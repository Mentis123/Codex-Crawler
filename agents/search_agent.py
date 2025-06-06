import os
from datetime import datetime, timedelta
import re
from openai import OpenAI
from llama_index.core import Document
from llama_index.readers.web import BeautifulSoupWebReader
from bs4 import BeautifulSoup
import requests
from serpapi import Client as SerpAPIClient
import json
import pytz

class SearchAgent:
    def __init__(self, config):
        self.config = config
        self.timeframe_days = config.get('lookback_days', config.get('search_timeframe_days', 7))
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.model = "o3-mini"
        self.min_articles = 6
        self.max_retries = 3
        self.request_timeout = 10  # seconds
        self.max_keywords = 5  # Limit number of keywords per search

    def extract_keywords_from_criteria(self, criteria_text):
        """
        Extract focused keywords from criteria
        """
        try:
            prompt = f"""
            Extract 5 specific and focused search keywords from the criteria below.
            Focus on technical terms that would yield relevant AI news articles.
            Return the keywords in this format: {{"keywords": ["keyword1", "keyword2", ...]}}

            Criteria:
            {criteria_text}
            """

            response = self.client.chat.completions.create(
                model="o3-mini",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)
            keywords = result.get('keywords', [])
            return keywords[:self.max_keywords]

        except Exception as e:
            print(f"Error extracting keywords: {str(e)}")
            return [
                "artificial intelligence news",
                "AI developments",
                "machine learning updates"
            ]

    def fetch_article_content(self, url):
        """
        Fetch and process article content using LlamaIndex with timeout
        """
        try:
            response = requests.get(url, timeout=self.request_timeout)
            soup = BeautifulSoup(response.text, 'html.parser')

            for element in soup(['script', 'style', 'meta', 'link', 'header', 'footer', 'nav']):
                element.decompose()

            article = soup.find('article') or soup.find('main') or soup.find('body')
            if article:
                return article.get_text(strip=True)
            return soup.get_text(strip=True)

        except Exception as e:
            print(f"Error fetching content from {url}: {str(e)}")
            return ""

    def parse_date(self, date_str):
        """Parse date with fallback"""
        try:
            return datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            try:
                return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                print(f"Could not parse date: {date_str}, using current time")
                return datetime.now()

    def search(self, criteria_text=None):
        """
        Aggregates articles from all configured sources with optimized validation flow
        """
        articles = []
        cutoff_time = datetime.now() - timedelta(days=self.timeframe_days)

        try:
            keywords = self.extract_keywords_from_criteria(criteria_text)[:self.max_keywords]

            print(f"Using cutoff time: {cutoff_time}")
            print(f"Searching with keywords: {keywords}")

            potential_articles = self._search_with_keywords(keywords, cutoff_time)
            print(f"Found {len(potential_articles)} potential articles")

            validated_articles = []
            for article in potential_articles:
                try:
                    content = extract_full_content(article['url'])
                    if content:
                        analysis = summarize_article(content)
                        if analysis:
                            validation = validate_ai_relevance({
                                **article,
                                'content': content,
                                **analysis
                            })

                            if validation['is_relevant']:
                                validated_articles.append({
                                    **article,
                                    'content': content,
                                    **analysis,
                                    'ai_confidence': 100,
                                    'ai_validation': validation['reason']
                                })
                                print(f"Validated article: {article['title']}")

                except Exception as e:
                    print(f"Error processing article {article['url']}: {str(e)}")
                    if "OpenAI API quota exceeded" in str(e):
                        raise
                    continue

            validated_articles.sort(key=lambda x: x['published_date'], reverse=True)

            print(f"Final validated article count: {len(validated_articles)}")
            return validated_articles

        except Exception as e:
            print(f"Error in search process: {str(e)}")
            raise

    def _search_with_keywords(self, keywords, cutoff_time):
        """Helper method to search with a set of keywords"""
        articles = []
        api_key = os.environ.get("SERPAPI_API_KEY")

        if not api_key:
            raise Exception("SERPAPI_API_KEY not found")

        client = SerpAPIClient(api_key=api_key)

        for keyword in keywords:
            try:
                params = {
                    "engine": "google",
                    "q": keyword,
                    "tbm": "nws",
                    "num": 5,  # Limit results per keyword
                }

                results = client.search(params).get("news_results", [])
                print(f"Found {len(results)} results for keyword: {keyword}")

                for result in results:
                    if not all(key in result for key in ['title', 'link', 'source']):
                        continue

                    metadata = extract_metadata(result['link'], cutoff_time)
                    if metadata and ce_is_specific_article({'title': result['title'], 'url': result['link']}):
                        articles.append({
                            'title': result['title'],
                            'url': result['link'],
                            'source': result['source'],
                            'published_date': metadata['date']
                        })

            except Exception as e:
                print(f"Error searching for keyword {keyword}: {str(e)}")
                continue

        return articles


from utils.content_extractor import (
    extract_metadata as ce_extract_metadata,
    extract_full_content as ce_extract_full_content,
    validate_ai_relevance as ce_validate_ai_relevance,
    is_specific_article as ce_is_specific_article,
)
from utils.common import parse_date
from utils.ai_analyzer import summarize_article as ai_summarize_article


def extract_metadata(url, cutoff_time):
    """Retrieve metadata for a URL and filter by cutoff time."""
    try:
        metadata = ce_extract_metadata(url, cutoff_time)
        if not metadata or 'date' not in metadata:
            return None

        date_val = metadata['date']
        if isinstance(date_val, str):
            parsed = parse_date(date_val)
            date_val = parsed or datetime.now()

        if not isinstance(date_val, datetime):
            return None

        if date_val.tzinfo:
            date_val = date_val.astimezone(pytz.UTC)
        else:
            date_val = pytz.UTC.localize(date_val)

        if not cutoff_time.tzinfo:
            cutoff_time = pytz.UTC.localize(cutoff_time)

        if date_val < cutoff_time:
            return None

        return {"date": date_val}
    except Exception as e:
        print(f"Metadata extraction failed for {url}: {e}")
        return None


def extract_full_content(url):
    """Return the full textual content of the article."""
    try:
        content = ce_extract_full_content(url)
        return content or ""
    except Exception as e:
        print(f"Content extraction failed for {url}: {e}")
        return ""


def summarize_article(content):
    """Summarize article content using the AI analyzer."""
    try:
        return ai_summarize_article(content)
    except Exception as e:
        print(f"Article summarization failed: {e}")
        return None


def validate_ai_relevance(article_data):
    """Check if an article is relevant to AI topics."""
    try:
        return ce_validate_ai_relevance(article_data)
    except Exception as e:
        print(f"AI relevance validation failed: {e}")
        return {"is_relevant": True, "reason": "Validation error"}
