import re
import time
import hashlib
import logging
import json
from typing import Dict, Any, List, Optional, Tuple

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
        self.model = config.get('model', 'gpt-4o-mini') if config else 'gpt-4o-mini'
        self.log_event("Analyzer agent initialized")
    
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
    
    def summarize_article(self, content: str) -> Optional[Dict[str, Any]]:
        """Generate a summary and takeaway for an article with caching"""
        # Check cache first
        content_hash = hashlib.md5(content[:10000].encode()).hexdigest()
        cache_key = f"summary:{content_hash}"
        
        if cache_key in self.cache:
            timestamp, cached_result = self.cache[cache_key]
            if time.time() - timestamp < (self.cache_duration * 3600):
                self.log_event(f"Using cached summary for content hash: {content_hash[:8]}")
                return cached_result
        
        # Process content in chunks if too large
        if len(content) > 12000:
            self.log_event(f"Content is large ({len(content)} chars), processing in chunks")
            chunks = self._split_into_chunks(content)
            chunk_summaries = []
            
            for i, chunk in enumerate(chunks):
                self.log_event(f"Processing chunk {i+1}/{len(chunks)}")
                summary = self._process_chunk(chunk)
                if summary:
                    chunk_summaries.append(summary)
            
            if not chunk_summaries:
                return None
                
            if len(chunk_summaries) == 1:
                result = chunk_summaries[0]
            else:
                result = self._combine_summaries(chunk_summaries)
        else:
            # Process directly if small enough
            result = self._process_chunk(content)
        
        # Cache result if valid
        if result:
            self.cache[cache_key] = (time.time(), result)
            return result
        
        return None
    
    def _split_into_chunks(self, content: str, max_chunk_size: int = 10000) -> List[str]:
        """Split content into smaller chunks for processing"""
        # Clean and normalize content
        content = re.sub(r'\s+', ' ', content.strip())
        
        if len(content) < max_chunk_size:
            return [content]
            
        # Split on sentence boundaries
        sentences = re.split(r'(?<=[.!?])\s+', content)
        chunks = []
        current_chunk = []
        current_size = 0
        
        for sentence in sentences:
            sentence_size = len(sentence)
            
            # Handle very long sentences
            if sentence_size > max_chunk_size:
                # Add current chunk if not empty
                if current_chunk:
                    chunks.append(' '.join(current_chunk))
                    current_chunk = []
                    current_size = 0
                
                # Split long sentence into fixed-size chunks
                for i in range(0, len(sentence), max_chunk_size):
                    chunks.append(sentence[i:i+max_chunk_size])
                continue
            
            # Start a new chunk if adding this sentence would exceed max size
            if current_size + sentence_size > max_chunk_size:
                chunks.append(' '.join(current_chunk))
                current_chunk = [sentence]
                current_size = sentence_size
            else:
                current_chunk.append(sentence)
                current_size += sentence_size
        
        # Add the last chunk if not empty
        if current_chunk:
            chunks.append(' '.join(current_chunk))
            
        self.log_event(f"Split content into {len(chunks)} chunks")
        return chunks
    
    def _process_chunk(self, chunk: str) -> Optional[Dict[str, Any]]:
        """Process a single chunk of content for summary and takeaway"""
        if len(chunk) < 100:
            return {"takeaway": "Content too short for meaningful analysis."}
            
        prompt = (
            "Analyze this article about AI and create a business-focused takeaway following these rules:\n\n"
            "1. Write a 3-4 sentence focused takeaway (70-90 words)\n"
            "2. Include specific company names mentioned in the article\n"
            "3. Include quantitative data when available (revenue, user counts, percentages)\n"
            "4. Only use statistics from the source text - never fabricate numbers\n"
            "5. Highlight business impacts and strategic benefits of the AI technology\n"
            "6. Use clear language without technical jargon\n\n"
            "Also extract 3-5 key points from the article.\n\n"
            "Response format: {\"takeaway\": \"...\", \"key_points\": [\"point 1\", \"point 2\", ...]}\n\n"
            f"Article content:\n{chunk[:12000]}"  # Limit chunk size
        )
        
        try:
            # Call AI model
            result = self.execute_ai_prompt(
                prompt=prompt,
                model=self.model,
                response_format="json_object"
            )
            
            if not result:
                self.log_event("Empty or invalid response from AI model", "warning")
                return {"takeaway": "Unable to generate takeaway from content."}
                
            # Ensure required fields exist
            if "takeaway" not in result:
                result["takeaway"] = "No takeaway available"
                
            if "key_points" not in result or not isinstance(result["key_points"], list):
                result["key_points"] = []
                
            return result
            
        except Exception as e:
            self.log_event(f"Error processing chunk: {str(e)}", "error")
            return {"takeaway": "Error occurred during content processing."}
    
    def _combine_summaries(self, summaries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Combine multiple chunk summaries into a single result"""
        if not summaries:
            return {"takeaway": "No content available to summarize."}
            
        if len(summaries) == 1:
            return summaries[0]
            
        # Combine takeaways and key points
        combined_takeaways = " ".join(s.get("takeaway", "") for s in summaries if s)
        all_key_points = []
        
        for summary in summaries:
            if summary and "key_points" in summary and isinstance(summary["key_points"], list):
                all_key_points.extend(summary["key_points"])
        
        # Request AI to synthesize a cohesive summary
        prompt = (
            "Combine these separate takeaways into a single business-focused summary:\n\n"
            f"{combined_takeaways}\n\n"
            "Follow these rules for your combined takeaway:\n"
            "1. Write 3-4 impactful sentences in a single paragraph (70-90 words total)\n"
            "2. Include specific company names from the original takeaways\n"
            "3. Include the most important quantitative data\n"
            "4. Focus on business impact and strategic implications\n"
            "5. Use clear, executive-friendly language\n\n"
            "Also synthesize these key points into the 4-5 most important ones:\n"
            f"{all_key_points}\n\n"
            "Response format: {\"takeaway\": \"...\", \"key_points\": [\"point 1\", \"point 2\", ...]}"
        )
        
        try:
            result = self.execute_ai_prompt(
                prompt=prompt,
                model=self.model,
                response_format="json_object"
            )
            
            if not result:
                # Fallback: use first summary
                self.log_event("Failed to combine summaries, using first summary", "warning")
                if summaries and len(summaries) > 0:
                    return summaries[0]
                return {"takeaway": "Unable to combine summaries."}
                
            # Ensure required fields exist
            if "takeaway" not in result:
                result["takeaway"] = summaries[0].get("takeaway", "No takeaway available")
                
            if "key_points" not in result or not isinstance(result["key_points"], list):
                for summary in summaries:
                    if "key_points" in summary and summary["key_points"]:
                        result["key_points"] = summary["key_points"][:5]
                        break
                else:
                    result["key_points"] = []
                    
            return result
            
        except Exception as e:
            self.log_event(f"Error combining summaries: {str(e)}", "error")
            # Return first summary as fallback
            if summaries and len(summaries) > 0:
                return summaries[0]
            return {"takeaway": "Error combining summaries."}
    
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