import requests
from serpapi import Client as SerpAPIClient
from datetime import datetime
import xml.etree.ElementTree as ET
import trafilatura
import os

def search_web(keywords, cutoff_date):
    """
    Searches for articles using SerpAPI
    """
    articles = []
    api_key = os.environ.get("SERPAPI_API_KEY")
    client = SerpAPIClient(api_key=api_key)

    for keyword in keywords:
        params = {
            "engine": "google",
            "q": f"{keyword} news",
            "tbm": "nws",
        }

        try:
            results = client.search(params).get("news_results", [])

            for result in results:
                pub_date = datetime.strptime(result['date'], '%Y-%m-%d')
                if pub_date >= cutoff_date:
                    articles.append({
                        'title': result['title'],
                        'url': result['link'],
                        'source': result['source'],
                        'published_date': pub_date,
                        'content': get_article_content(result['link'])
                    })
        except Exception as e:
            print(f"Error searching for keyword {keyword}: {str(e)}")

    return articles

def search_arxiv(cutoff_date):
    """
    Searches for articles on ArXiv
    """
    articles = []
    url = "https://export.arxiv.org/api/query"
    params = {
        "search_query": "all:artificial intelligence",
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "max_results": 5,
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        root = ET.fromstring(response.text)

        ns = {"a": "http://www.w3.org/2005/Atom"}
        for entry in root.findall("a:entry", ns):
            title = entry.findtext("a:title", default="", namespaces=ns).strip()
            link = entry.findtext("a:id", default="", namespaces=ns).strip()
            date_text = entry.findtext("a:published", default="", namespaces=ns)
            summary = entry.findtext("a:summary", default="", namespaces=ns).strip()

            try:
                pub_date = datetime.strptime(date_text[:10], "%Y-%m-%d")
            except Exception:
                pub_date = cutoff_date

            if pub_date >= cutoff_date:
                articles.append({
                    "title": title,
                    "url": link,
                    "source": "arXiv",
                    "published_date": pub_date,
                    "content": summary,
                })
    except Exception as e:
        print(f"Error searching arXiv: {str(e)}")

    return articles

def scrape_website(url, source_name, cutoff_date):
    """
    Scrapes articles from a specific website
    """
    articles = []
    downloaded = trafilatura.fetch_url(url)

    if downloaded:
        content = trafilatura.extract(downloaded)
        if content:
            articles.append({
                'title': source_name,  # Would need better title extraction
                'url': url,
                'source': source_name,
                'published_date': datetime.now(),  # Would need better date extraction
                'content': content
            })

    return articles

def get_article_content(url):
    """
    Extracts content from article URL
    """
    try:
        downloaded = trafilatura.fetch_url(url)
        content = trafilatura.extract(downloaded)
        return content or ""
    except Exception:
        return ""