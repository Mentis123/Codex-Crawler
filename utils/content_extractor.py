# Importing ThreadPoolExecutor inside process_batch to fix the scope issue.
import trafilatura
import pandas as pd
from typing import List, Dict, Optional, Tuple, Any
import requests
from bs4 import BeautifulSoup
import logging
import time
from datetime import datetime, timedelta
import pytz
from urllib.parse import urljoin
import re
import functools
import hashlib
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Thread

# Configure logging
logger = logging.getLogger(__name__)

# Simple cache for web requests and extracted content
_content_cache = {}
_metadata_cache = {}

class TooManyRequestsError(Exception):
    pass

def cache_content(max_age_seconds=3600):
    """Decorator to cache content extraction results"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Create a cache key based on the URL (first argument to most functions)
            if not args or not isinstance(args[0], str):
                return func(*args, **kwargs)

            url = args[0]
            cache_key = f"{func.__name__}:{url}"

            # Check if we have a valid cached result
            if cache_key in _content_cache:
                timestamp, result = _content_cache[cache_key]
                if time.time() - timestamp < max_age_seconds:
                    logger.info(f"Using cached content for {url}")
                    return result

            # Call the function and cache the result
            result = func(*args, **kwargs)
            if result:  # Only cache successful results
                _content_cache[cache_key] = (time.time(), result)
            return result

        return wrapper
    return decorator

def load_source_sites(test_mode: bool = False) -> List[str]:
    """Load the source sites from the CSV file."""
    try:
        df = pd.read_csv('data/search_sites.csv', header=None)
        sites = df[0].tolist()

        # Remove any empty strings or invalid URLs
        sites = [site.strip() for site in sites if isinstance(site, str) and site.strip()]

        # Ensure we don't process duplicate sites
        sites = list(dict.fromkeys(sites))

        if test_mode:
            logger.info("Running in test mode - using Wired.com only")
            return ['https://www.wired.com/tag/artificial-intelligence/']

        logger.info(f"Loaded {len(sites)} source sites for crawling")
        return sites
    except Exception as e:
        logger.error(f"Error loading source sites: {e}")
        return []

@cache_content(max_age_seconds=21600)  # Cache for 6 hours
def extract_metadata(url: str, cutoff_time: datetime) -> Optional[Dict[str, str]]:
    """Extract and validate metadata with caching and improved error handling."""
    import json  # Import at function level to ensure it's available

    try:
        # Check if we already have the metadata cached
        cache_key = f"metadata:{url}"
        if cache_key in _metadata_cache:
            timestamp, meta_data = _metadata_cache[cache_key]
            if time.time() - timestamp < 21600:  # 6 hours
                logger.info(f"Using cached metadata for {url}")
                return meta_data

        # Fetch the content - trafilatura doesn't support timeout parameter directly
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            logger.warning(f"Failed to download content from {url}")
            return None

        # Use trafilatura to extract metadata
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
                meta_dict = json.loads(metadata)
                result = {
                    'title': meta_dict.get('title', '').strip(),
                    'date': meta_dict.get('date', datetime.now(pytz.UTC).strftime('%Y-%m-%d')),
                    'url': url
                }

                # Cache the result
                _metadata_cache[cache_key] = (time.time(), result)
                return result

            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing error for {url}: {e}")
                # Fallback metadata
                result = {
                    'title': "Article from " + url.split('/')[2],
                    'date': datetime.now(pytz.UTC).strftime('%Y-%m-%d'),
                    'url': url
                }
                return result

    except Exception as e:
        logger.error(f"Error extracting metadata from {url}: {str(e)}")
        return None

    return None

@cache_content(max_age_seconds=43200)  # Cache for 12 hours
def extract_full_content(url: str) -> Optional[str]:
    """Extract full content with caching and smart retries."""
    max_retries = 3
    retry_delay = 2  # Start with a 2-second delay

    for attempt in range(max_retries):
        try:
            # Use trafilatura to get content
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
                    # Clean whitespace and normalize content
                    content = re.sub(r'\s+', ' ', content).strip()
                    return content

            # Exponential backoff between retries
            if attempt < max_retries - 1:
                # Wait longer between each attempt (exponential backoff)
                wait_time = retry_delay * (2 ** attempt)
                logger.info(f"Retry {attempt+1}/{max_retries} for {url} in {wait_time}s")
                time.sleep(wait_time)

        except Exception as e:
            logger.error(f"Error extracting content from {url} (attempt {attempt + 1}): {str(e)}")
            if attempt < max_retries - 1:
                # Wait longer between each attempt (exponential backoff)
                wait_time = retry_delay * (2 ** attempt)
                logger.info(f"Retry {attempt+1}/{max_retries} for {url} in {wait_time}s")
                time.sleep(wait_time)

    logger.warning(f"Failed to extract content from {url} after {max_retries} attempts")
    return None

def is_consent_or_main_page(text: str) -> bool:
    """Check if the page is a consent form or main landing page."""
    consent_indicators = [
        'cookie policy',
        'privacy notice',
        'consent form',
        'accept cookies',
        'terms of use',
        'privacy policy'
    ]
    text_lower = text.lower()
    return any(indicator in text_lower for indicator in consent_indicators)

def make_request_with_backoff(url: str, max_retries: int = 3, initial_delay: int = 5) -> Optional[requests.Response]:
    """Make HTTP request with exponential backoff."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    for attempt in range(max_retries):
        try:
            delay = initial_delay * (2 ** attempt)
            if attempt > 0:
                time.sleep(delay)

            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            return response

        except requests.exceptions.RequestException as e:
            logger.error(f"Request error for {url} (attempt {attempt + 1}): {str(e)}")
            if attempt == max_retries - 1:
                raise

    return None

def similar_titles(title1: str, title2: str) -> bool:
    """Checks if two titles are similar (simplified example)."""
    # Replace with a more robust similarity check if needed (e.g., using difflib)
    return title1.lower() == title2.lower()

def validate_ai_relevance(article_data):
    """Validate if an article is meaningfully about AI technology or applications."""
    title = article_data.get('title', '').lower()
    summary = article_data.get('summary', '').lower()
    content = article_data.get('content', '').lower()

    # Check if the title explicitly mentions AI
    if any(term in title for term in ['ai', 'artificial intelligence', 'machine learning', 'chatgpt', 'generative']):
        return {
            "is_relevant": True,
            "reason": f"Direct AI mention in title: {article_data.get('title')}"
        }

    # If found in potential AI articles, consider it relevant
    if "Found potential AI article:" in article_data.get('_source_log', ''):
        return {
            "is_relevant": True,
            "reason": "Identified as potential AI article during initial scan"
        }

    return {
        "is_relevant": True,  # Default to including articles that made it this far
        "reason": "Passed initial AI content scan"
    }

def is_specific_article(metadata: Dict[str, str]) -> bool:
    """
    Validate if the content represents a specific article rather than a category/section page.
    Applied after finding AI articles, before presenting to user.

    Returns:
        bool: True if content appears to be a specific article, False otherwise
    """
    if not metadata:
        return False

    title = metadata.get('title', '').lower()
    url = metadata.get('url', '').lower()

    # Only exclude obvious non-articles
    url_patterns_to_exclude = [
        r'/privacy\b',
        r'/terms\b',
        r'/about\b',
        r'/contact\b'
    ]

    if any(re.search(pattern, url) for pattern in url_patterns_to_exclude):
        logger.info(f"Excluding non-article URL: {url}")
        return False

    # Accept more titles, only exclude extremely short ones
    if len(title.split()) < 2 and len(title) < 5:
        logger.info(f"Excluding too short title: {title}")
        return False

    return True

def clean_article_title(title):
    """Remove 'Permalink to' prefix and other common prefixes from article titles"""
    if title.startswith("Permalink to "):
        return title[len("Permalink to "):]
    return title

def process_link(link, source_url, ai_regex, cutoff_time, seen_urls):
    """Process a single link to determine if it's an AI-related article"""
    try:
        href = link['href']
        if not href.startswith(('http://', 'https://')):
            href = urljoin(source_url, href)

        # Skip if we've already processed this URL
        if href in seen_urls:
            return None

        link_text = (link.text or '').strip()
        title = link.get('title', '').strip() or link_text

        # Clean the title to remove any "Permalink to" prefix
        title = clean_article_title(title)

        # Check if title contains AI-related keywords
        if not ai_regex.search(title):
            return None

        logger.info(f"Found potential AI article: {title}")
        metadata = extract_metadata(href, cutoff_time)

        if not metadata:
            return None

        # Parse the article date
        try:
            article_date = datetime.strptime(metadata['date'], '%Y-%m-%d')
            # Add UTC timezone to match cutoff_time
            article_date = pytz.UTC.localize(article_date)

            # Ensure cutoff_time is timezone aware
            if not cutoff_time.tzinfo:
                cutoff_time = pytz.UTC.localize(cutoff_time)

            # Add debugging for date comparison
            logger.info(f"Article date: {article_date}, Cutoff time: {cutoff_time}")
            # Only add articles that are newer than or equal to cutoff time
            if article_date >= cutoff_time:
                logger.info(f"Found AI article within time range: {title}")
                # Ensure the title is cleaned before adding to articles
                cleaned_title = clean_article_title(title)
                return {
                    'title': cleaned_title,
                    'url': href,
                    'date': metadata['date'],
                    'source': source_url,
                    'takeaway': ''  # Will be populated by AI analyzer
                }
            else:
                logger.info(f"Skipping article older than cutoff: {title} ({metadata['date']}) - Expected newer than {cutoff_time}")
                return None
        except ValueError as e:
            logger.error(f"Error parsing date for article {title}: {e}")
            return None

    except Exception as e:
        logger.error(f"Error processing link: {str(e)}")
        return None

def find_ai_articles(source_url, cutoff_time):
    """Find AI-related articles from a source URL using parallel processing"""
    logger.info(f"Searching with cutoff time: {cutoff_time}")
    articles = []
    seen_urls = set()
    source_status = {
        'url': source_url,
        'processed': False,
        'error': None,
        'article_count': 0
    }

    try:
        # Validate URL format
        if not source_url.startswith(('http://', 'https://')):
            source_url = f'https://{source_url}'

        logger.info(f"Processing source: {source_url}")

        # Cache key for this source request
        cache_key = f"source_content:{source_url}"
        response_text = None

        # Check cache first
        if cache_key in _content_cache:
            timestamp, cached_content = _content_cache[cache_key]
            # Use cache if less than 1 hour old
            if time.time() - timestamp < 3600:
                logger.info(f"Using cached source content for {source_url}")
                response_text = cached_content

        # Fetch if not cached
        if not response_text:
            response = make_request_with_backoff(source_url)
            if not response:
                logger.error(f"Could not fetch content from {source_url}")
                return []

            if response.status_code != 200:
                logger.error(f"Failed to fetch {source_url}: Status {response.status_code}")
                return []

            response_text = response.text
            # Cache the response
            _content_cache[cache_key] = (time.time(), response_text)

        soup = BeautifulSoup(response_text, 'html.parser')

        # Updated AI patterns with optimized regex
        ai_patterns = [
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

        ai_regex = re.compile('|'.join(ai_patterns), re.IGNORECASE)
        logger.info(f"Scanning URL: {source_url}")

        # Get all links with href
        all_links = soup.find_all('a', href=True)

        # Process links in parallel for efficiency - when more than 5 links
        if len(all_links) > 5:
            # Create thread pool
            with ThreadPoolExecutor(max_workers=5) as executor:
                # Submit all links for processing
                future_to_link = {
                    executor.submit(process_link, link, source_url, ai_regex, cutoff_time, seen_urls): link 
                    for link in all_links
                }

                # Process results as they complete
                for future in as_completed(future_to_link):
                    result = future.result()
                    if result and result['url'] not in seen_urls:
                        articles.append(result)
                        seen_urls.add(result['url'])
        else:
            # Process sequentially for small numbers of links
            for link in all_links:
                result = process_link(link, source_url, ai_regex, cutoff_time, seen_urls)
                if result and result['url'] not in seen_urls:
                    articles.append(result)
                    seen_urls.add(result['url'])

        logger.info(f"Found {len(articles)} articles from {source_url}")
        source_status['processed'] = True
        source_status['article_count'] = len(articles)
        logger.info(f"Successfully processed {source_url}: found {len(articles)} articles")
        return articles

    except Exception as e:
        error_msg = f"Error finding AI articles from {source_url}: {str(e)}"
        logger.error(error_msg)
        source_status['error'] = error_msg
        source_status['processed'] = True
        return []

def process_batch(sources, cutoff_time, db, seen_urls, status_placeholder):
    """Process a batch of sources with parallel article handling and caching"""
    from concurrent.futures import ThreadPoolExecutor
    batch_articles = []
    
    try:
        for source_url in sources:
            # Find articles for this source
            articles = find_ai_articles(source_url, cutoff_time)
            if articles:
                logger.info(f"Found {len(articles)} articles from {source_url}")
                batch_articles.extend(articles)
                
                # Update seen URLs to avoid duplicates
                for article in articles:
                    seen_urls.add(article['url'])
                    
        logger.info(f"Total articles in batch: {len(batch_articles)}")
        return batch_articles
            
    except Exception as e:
        logger.error(f"Error in process_batch: {str(e)}")
        # Return any articles we found before the error
        return batch_articles