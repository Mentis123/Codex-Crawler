import re
import time
import hashlib
import logging
import json
from typing import Dict, Any, List, Optional, Tuple

from utils.config_manager import load_config, DEFAULT_CONFIG
from utils import ai_analyzer as util_ai_analyzer # Added import

from agents.base_agent import BaseAgent

# Configure logging
logger = logging.getLogger(__name__)

class AnalyzerAgent(BaseAgent):
    """
    Agent responsible for article content analysis, summarization,
    and relevance validation
    """
    
    def __init__(self, config=None):
        """Initialize the analyzer agent with configuration"""
        super().__init__(config)
        self.cache = {}
        self.cache_duration = config.get('cache_duration_hours', 12) if config else 12
        # self.model = config.get('model', 'gpt-4o') if config else 'gpt-4o' # Model is handled by util_ai_analyzer
        self.log_event("Analyzer agent initialized")

    # _get_takeaway_rubric is no longer needed here as util_ai_analyzer handles it.
    
    def process(self, articles: List[Dict]) -> List[Dict]:
        """Process a list of articles for analysis"""
        self.log_event(f"Analyzing {len(articles)} articles")
        
        analyzed_articles = []
        for article in articles:
            try:
                if 'content' not in article or not article['content']:
                    # If article doesn't have content yet, try to get it from crawler
                    self.log_event(f"Article missing content: {article['title']}")
                    continue
                
                result = self.analyze_article(article)
                if result and self.is_relevant(result):
                    analyzed_articles.append(result)
                    self.log_event(f"Analyzed and validated article: {article['title']}")
                else:
                    self.log_event(f"Article not relevant or analysis failed: {article['title']}")
            except Exception as e:
                self.log_event(f"Error analyzing article {article.get('title', 'Unknown')}: {str(e)}", "error")
        
        self.log_event(f"Analysis complete. {len(analyzed_articles)} articles passed validation")
        return analyzed_articles
    
    def analyze_article(self, article: Dict) -> Optional[Dict]:
        """Analyze a single article with summarization and validation"""
        content = article.get('content')
        if not content:
            return None
            
        # Get article summary and takeaway
        summary_data = self.summarize_article(content)
        if not summary_data:
            return None
            
        # Validate relevance
        validation = self.validate_ai_relevance({
            **article,
            **summary_data
        })

        # Combine everything
        return {
            **article,
            **summary_data,
            'ai_validation': validation.get('reason', 'Unknown'),
            'ai_confidence': validation.get('confidence', 0)
        }

    def is_relevant(self, analyzed_article: Dict) -> bool:
        """Determine if an analyzed article should be kept."""
        confidence = analyzed_article.get('ai_confidence', 0)
        validation = analyzed_article.get('ai_validation')
        return confidence >= 40 and bool(validation)
    
    def summarize_article(self, content: str) -> Optional[Dict[str, Any]]:
        """Generate a summary and takeaway for an article with caching"""
        # Check cache first
        content_hash = hashlib.md5(content[:10000].encode()).hexdigest() # Use a portion for hashing
        cache_key = f"summary:{content_hash}"
        
        if cache_key in self.cache:
            timestamp, cached_result = self.cache[cache_key]
            if time.time() - timestamp < (self.cache_duration * 3600): # cache_duration in hours
                self.log_event(f"Using cached summary (AnalyzerAgent cache) for content hash: {content_hash[:8]}")
                return cached_result
        
        # Delegate to the centralized ai_analyzer utility
        # This call will use its own caching, validation, and refinement logic
        result = util_ai_analyzer.summarize_article(content)
        
        # Cache result if valid
        if result and result.get("takeaway") not in [
            "Article content is too short or empty.",
            "Unable to process content.",
            "Content could not be processed properly.",
            "Error combining article summaries.",
            "Unable to analyze content at this time."
        ] : # Basic check for valid result
            self.cache[cache_key] = (time.time(), result)
            self.log_event(f"Cached new summary (AnalyzerAgent cache) for content hash: {content_hash[:8]}")
            return result
        
        self.log_event(f"Failed to generate or cache summary for content hash: {content_hash[:8]}. Result: {result}", "warning")
        return result # Return result even if it's an error message, or None if summarize_article failed badly

    def validate_ai_relevance(self, article_data: Dict) -> Dict:
        """Validate if an article is meaningfully about AI technology or applications"""
        # Extract relevant fields for validation
        title = article_data.get('title', '').lower()
        takeaway = article_data.get('takeaway', '').lower()
        content_sample = article_data.get('content', '')[:5000].lower()
        
        # Score tracking
        confidence = 0
        reason = "Not explicitly about AI"
        
        # Title validation (high weight)
        ai_terms_title = ['ai', 'artificial intelligence', 'machine learning', 'chatgpt', 
                          'generative ai', 'large language model', 'llm']
        
        for term in ai_terms_title:
            if term in title:
                confidence += 50
                reason = f"AI term '{term}' found in title"
                break
                
        # Content validation (medium weight)
        if confidence < 50:
            # Count AI terms in content
            ai_term_count = 0
            ai_terms_content = ai_terms_title + ['neural network', 'deep learning', 'algorithm', 
                                                'data science', 'model', 'gpt', 'transformer']
                                        
            for term in ai_terms_content:
                if term in content_sample:
                    ai_term_count += content_sample.count(term)
                    
            if ai_term_count >= 5:
                confidence += 40
                reason = f"Multiple AI references ({ai_term_count}) found in content"
                
        # Takeaway validation (medium weight)
        if confidence < 70 and takeaway:
            for term in ai_terms_title:
                if term in takeaway:
                    confidence += 30
                    reason = f"AI term '{term}' found in article takeaway"
                    break
        
        # Default to pass for articles that made it this far
        is_relevant = confidence >= 40
        
        return {
            "is_relevant": is_relevant,
            "confidence": confidence,
            "reason": reason
        }
