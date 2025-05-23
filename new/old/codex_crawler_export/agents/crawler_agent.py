import os
import re
import time
import logging
import hashlib
import requests
from datetime import datetime, timedelta
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import pytz
import trafilatura
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional, Set

from agents.base_agent import BaseAgent

# Configure logging
logger = logging.getLogger(__name__)

class CrawlerAgent(BaseAgent):
    """
    Agent responsible for crawling websites, extracting links,
    and fetching article content
    """
    
    def __init__(self, config=None):
        """Initialize the crawler agent with configuration"""
        super().__init__(config)
        self.content_cache = {}
        self.metadata_cache = {}
        self.max_workers = config.get('max_crawler_workers', 3) if config else 3
        self.cache_duration = config.get('cache_duration_hours', 6) if config else 6
        self.request_timeout = config.get('request_timeout', 10) if config else 10
        self.max_retries = config.get('max_retries', 3) if config else 3
        self.ai_patterns = [
            r'\b[Aa][Ii]\b',  # Standalone "AI"
            r'\b[Aa][Ii]-[a-zA-Z]+\b',  # AI-powered, AI-driven, etc.
            r'\b[a-zA-Z]+-[Aa][Ii]\b',  # gen-AI, etc.
            r'\bartificial intelligence\b',
            r'\bmachine learning\b',
            r'\bdeep learning\b',
            r'\bneural network\b',
            r'\bgenerative ai\b',
            r'\bchatgpt\b',
            r'\blarge language model\b',
            r'\bllm\b'
        ]
        self.ai_regex = re.compile('|'.join(self.ai_patterns), re.IGNORECASE)
        self.log_event("Crawler agent initialized")
    
    def process(self, source_urls, cutoff_time=None):
        """Process a list of source URLs to find AI-related articles"""
        if cutoff_time is None:
            days = self.config.get('default_days', 7)
            cutoff_time = datetime.now() - timedelta(days=days)
            
        self.log_event(f"Starting crawl of {len(source_urls)} sources with cutoff: {cutoff_time}")
        
        all_articles = []
        seen_urls = set()
        
        for source_url in source_urls:
            try:
                self.log_event(f"Processing source: {source_url}")
                articles = self.crawl_source(source_url, cutoff_time, seen_urls)
                all_articles.extend(articles)
                self.log_event(f"Found {len(articles)} articles from {source_url}")
            except Exception as e:
                self.log_event(f"Error crawling {source_url}: {str(e)}", "error")
        
        self.log_event(f"Crawling complete. Found {len(all_articles)} total articles")
        return all_articles
    
    def crawl_source(self, source_url: str, cutoff_time: datetime, seen_urls: Set[str]) -> List[Dict]:
        """Crawl a single source URL to find AI-related articles"""
        # Normalize URL
        if not source_url.startswith(('http://', 'https://')):
            source_url = f'https://{source_url}'
            
        # Fetch page content (with caching)
        html_content = self.fetch_page_with_cache(source_url)
        if not html_content:
            return []
            
        # Parse HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find all links
        links = soup.find_all('a', href=True)
        
        # Process links - either in parallel or sequentially based on count
        articles = []
        if len(links) > 5:
            # Parallel processing for many links
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit all links for processing
                future_to_link = {
                    executor.submit(self.process_link, link, source_url, cutoff_time, seen_urls): link 
                    for link in links
                }
                
                # Collect results as they complete
                for future in as_completed(future_to_link):
                    result = future.result()
                    if result and result['url'] not in seen_urls:
                        articles.append(result)
                        seen_urls.add(result['url'])
        else:
            # Sequential processing for few links
            for link in links:
                result = self.process_link(link, source_url, cutoff_time, seen_urls)
                if result and result['url'] not in seen_urls:
                    articles.append(result)
                    seen_urls.add(result['url'])
        
        return articles
    
    def process_link(self, link, source_url: str, cutoff_time: datetime, seen_urls: Set[str]) -> Optional[Dict]:
        """Process a single link to determine if it's an AI-related article"""
        try:
            href = link['href']
            if not href.startswith(('http://', 'https://')):
                href = urljoin(source_url, href)

            # Skip if already processed
            if href in seen_urls:
                return None

            # Extract text from link
            link_text = (link.text or '').strip()
            title = link.get('title', '').strip() or link_text

            # Clean title
            if title.startswith("Permalink to "):
                title = title[len("Permalink to "):]

            # Check if title contains AI-related keywords
            if not self.ai_regex.search(title):
                return None
                
            self.log_event(f"Found potential AI article: {title}")
            
            # Extract metadata
            metadata = self.extract_metadata(href, cutoff_time)
            if not metadata:
                return None
                
            # Validate date against cutoff
            try:
                article_date = datetime.strptime(metadata['date'], '%Y-%m-%d')
                article_date = pytz.UTC.localize(article_date)

                # Ensure cutoff time is timezone aware
                if not cutoff_time.tzinfo:
                    cutoff_time = pytz.UTC.localize(cutoff_time)

                # Only include articles after cutoff date
                if article_date >= cutoff_time:
                    self.log_event(f"Found AI article within timeframe: {title}")
                    return {
                        'title': title,
                        'url': href,
                        'date': metadata['date'],
                        'source': source_url,
                        'content': None  # Content will be fetched separately
                    }
                else:
                    self.log_event(f"Article too old, skipping: {title}")
                    return None
            except ValueError as e:
                self.log_event(f"Date parsing error for {title}: {e}", "error")
                return None

        except Exception as e:
            self.log_event(f"Error processing link: {str(e)}", "error")
            return None
    
    def fetch_page_with_cache(self, url: str) -> Optional[str]:
        """Fetch a web page with caching"""
        cache_key = f"page:{url}"
        
        # Check cache first
        if cache_key in self.content_cache:
            timestamp, cached_content = self.content_cache[cache_key]
            if time.time() - timestamp < (self.cache_duration * 3600):  # Cache duration in hours
                self.log_event(f"Using cached page for {url}")
                return cached_content
        
        # Fetch if not cached
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            for attempt in range(self.max_retries):
                try:
                    if attempt > 0:
                        # Exponential backoff
                        wait_time = 2 ** attempt
                        self.log_event(f"Retry {attempt+1}/{self.max_retries} for {url}, waiting {wait_time}s")
                        time.sleep(wait_time)
                        
                    response = requests.get(url, headers=headers, timeout=self.request_timeout)
                    response.raise_for_status()
                    
                    # Cache the result
                    self.content_cache[cache_key] = (time.time(), response.text)
                    return response.text
                    
                except (requests.RequestException, ConnectionError) as e:
                    if attempt == self.max_retries - 1:
                        raise
                    self.log_event(f"Request error on attempt {attempt+1}: {str(e)}", "warning")
                    
        except Exception as e:
            self.log_event(f"Error fetching {url}: {str(e)}", "error")
            return None
    
    def extract_metadata(self, url: str, cutoff_time: datetime) -> Optional[Dict]:
        """Extract metadata from an article URL with caching"""
        cache_key = f"metadata:{url}"
        
        # Check cache first
        if cache_key in self.metadata_cache:
            timestamp, cached_metadata = self.metadata_cache[cache_key]
            if time.time() - timestamp < (self.cache_duration * 3600):
                self.log_event(f"Using cached metadata for {url}")
                return cached_metadata
        
        # Extract if not cached
        try:
            downloaded = trafilatura.fetch_url(url)
            if not downloaded:
                self.log_event(f"Failed to download content from {url}")
                return None
                
            metadata = trafilatura.extract(
                downloaded,
                include_links=True,
                include_images=True,
                include_tables=True,
                with_metadata=True,
                output_format='json',
                favor_recall=True
            )
            
            if metadata:
                try:
                    import json
                    meta_dict = json.loads(metadata)
                    result = {
                        'title': meta_dict.get('title', '').strip(),
                        'date': meta_dict.get('date', datetime.now(pytz.UTC).strftime('%Y-%m-%d')),
                        'url': url
                    }
                    
                    # Cache the result
                    self.metadata_cache[cache_key] = (time.time(), result)
                    return result
                    
                except json.JSONDecodeError as e:
                    self.log_event(f"JSON parsing error for {url}: {e}", "error")
                    # Fallback metadata
                    result = {
                        'title': "Article from " + url.split('/')[2],
                        'date': datetime.now(pytz.UTC).strftime('%Y-%m-%d'),
                        'url': url
                    }
                    return result
                    
        except Exception as e:
            self.log_event(f"Error extracting metadata from {url}: {str(e)}", "error")
            return None
            
        return None
    
    def extract_full_content(self, url: str) -> Optional[str]:
        """Extract full content from an article URL with caching"""
        cache_key = f"content:{url}"
        
        # Check cache first
        if cache_key in self.content_cache:
            timestamp, cached_content = self.content_cache[cache_key]
            if time.time() - timestamp < (self.cache_duration * 3600):
                self.log_event(f"Using cached content for {url}")
                return cached_content
        
        # Extract if not cached
        for attempt in range(self.max_retries):
            try:
                downloaded = trafilatura.fetch_url(url)
                if downloaded:
                    content = trafilatura.extract(
                        downloaded,
                        include_links=True,
                        include_images=True,
                        include_tables=True,
                        with_metadata=False,
                        favor_recall=True
                    )
                    
                    if content:
                        # Clean and normalize content
                        content = re.sub(r'\s+', ' ', content).strip()
                        
                        # Cache the result
                        self.content_cache[cache_key] = (time.time(), content)
                        return content
                        
                # Retry with exponential backoff
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt
                    self.log_event(f"Retry {attempt+1}/{self.max_retries} for content extraction from {url}")
                    time.sleep(wait_time)
                    
            except Exception as e:
                self.log_event(f"Error extracting content from {url}: {str(e)}", "error")
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
                    
        self.log_event(f"Failed to extract content from {url} after {self.max_retries} attempts", "warning")
        return None