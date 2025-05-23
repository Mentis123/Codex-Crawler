
import os
from openai import OpenAI
import json
from typing import Dict, Any, Optional, List
import re
import logging
import functools
import hashlib
import time

# Configure logging
logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Simple in-memory cache for API responses
_cache = {}

def cache_result(func):
    """Cache decorator for expensive API calls"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Create a cache key based on function name and arguments
        cache_key = f"{func.__name__}:{hashlib.md5(str(args).encode()).hexdigest()}"
        
        # If result exists in cache and is less than 6 hours old, return it
        if cache_key in _cache:
            timestamp, result = _cache[cache_key]
            if time.time() - timestamp < 21600:  # 6 hours
                logger.info(f"Using cached result for {func.__name__}")
                return result
        
        # Otherwise, call the function and cache the result
        result = func(*args, **kwargs)
        _cache[cache_key] = (time.time(), result)
        return result
    
    return wrapper

def split_into_chunks(content: str, max_chunk_size: int = 40000) -> List[str]:
    """Split content into smaller chunks to avoid processing issues."""
    # Clean and normalize content - more efficient regex
    content = re.sub(r'\s+', ' ', content.strip())

    # Quick return for small content
    if len(content) < max_chunk_size * 3:  # ~3 chars per token
        return [content]

    # Improved sentence splitting with better boundary handling
    sentences = re.split(r'(?<=[.!?])\s+', content)
    chunks = []
    current_chunk = []
    current_size = 0
    char_per_token = 3  
    max_chunk_chars = max_chunk_size * char_per_token

    for sentence in sentences:
        sentence_chars = len(sentence)

        # Handle very long sentences more efficiently
        if sentence_chars > max_chunk_chars:
            logger.warning(f"Very long sentence ({sentence_chars} chars) will be truncated")
            # Append existing chunk if any
            if current_chunk:
                chunks.append(' '.join(current_chunk))
                current_chunk = []
                current_size = 0
            
            # Create chunks from the long sentence
            for i in range(0, len(sentence), max_chunk_chars):
                chunks.append(sentence[i:i+max_chunk_chars])
            continue

        # Start a new chunk if the current one would exceed the limit
        if current_size + sentence_chars > max_chunk_chars:
            chunks.append(' '.join(current_chunk))
            current_chunk = [sentence]
            current_size = sentence_chars
        else:
            current_chunk.append(sentence)
            current_size += sentence_chars

    # Don't forget the last chunk
    if current_chunk:
        chunks.append(' '.join(current_chunk))

    logger.info(f"Split content into {len(chunks)} chunks (max size: {max_chunk_size} tokens)")
    return chunks

@cache_result
def _process_chunk(chunk: str) -> Optional[Dict[str, Any]]:
    """Process a single chunk of content with caching to avoid redundant API calls."""
    try:
        # Limit chunk size to avoid excessive token usage
        if len(chunk) > 150000:
            logger.warning(f"Chunk too large ({len(chunk)} chars), truncating...")
            chunk = chunk[:150000] + "..."

        prompt = (
            "Analyze this text and create a business-focused takeaway following these STRICT RULES:\n\n" +
            "1. Write EXACTLY 3-4 impactful sentences in a single paragraph (70-90 words total)\n" +
            "2. ALWAYS include specific company names mentioned in the article\n" +
            "3. MUST include REAL quantitative data when available ($16.6 billion, 200,000 users, 45% improvement)\n" +
            "4. DO NOT fabricate or estimate statistics - use ONLY numbers from the source text\n" +
            "5. Highlight measurable ROI, cost savings, revenue gains, or performance improvements\n" +
            "6. Clearly explain HOW companies are using AI and the SPECIFIC strategic benefits\n" +
            "7. Use clear, plain language without technical jargon\n" +
            "8. Include strategic business implications that explain WHY this matters\n" +
            "9. Format all numbers consistently with proper spacing and commas\n" +
            "10. Stay professional - NO promotional language or generic claims\n\n" +
            "Respond with valid JSON only: {\"takeaway\": \"Your concise takeaway here\"}\n" +
            "Ensure your JSON has properly closed quotes and braces.\n\n" + 
            chunk
        )

        try:
            # Use an explicit model with timeout and retry mechanism
            response = client.chat.completions.create(
                model="gpt-4o-mini",  # Using gpt-4o-mini for better balance of speed and quality
                messages=[
                    {"role": "system", "content": "You are a JSON generator. You must return ONLY valid, complete JSON in format {\"takeaway\": \"text\"}. Ensure all quotes are properly escaped and closed."},
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=2000,
                response_format={"type": "json_object"},
                timeout=30
            )
        except Exception as api_error:
            logger.error(f"API error during processing: {str(api_error)}")
            # Return placeholder on API error to avoid cascading failures
            return {"takeaway": "Unable to process content due to API limitations."}

        if not response or not response.choices or not response.choices[0].message:
            logger.warning("Empty response received from API")
            return {"takeaway": "Error: Empty response from AI"}
            
        content = response.choices[0].message.content
        if content:
            content = content.strip()
            try:
                return json.loads(content)
            except json.JSONDecodeError as json_err:
                logger.warning(f"JSON decode error: {json_err} - Content: {content[:100]}...")
                
                # Progressive fallback for malformed JSON
                # First try a more precise pattern for quoted takeaway
                takeaway_match = re.search(r'"takeaway"\s*:\s*"((?:[^"\\]|\\.)*)(?:"|\Z)', content)
                if takeaway_match:
                    return {"takeaway": takeaway_match.group(1)}
                    
                # Try an alternate pattern that just gets everything between the quotes
                takeaway_match = re.search(r'"takeaway"\s*:\s*"([^"]*)', content)
                if takeaway_match:
                    return {"takeaway": takeaway_match.group(1)}
                    
                # As a last resort, just try to extract any text after the takeaway key
                takeaway_match = re.search(r'"takeaway"\s*:\s*["\']?([^"}\']+)', content)
                if takeaway_match:
                    return {"takeaway": takeaway_match.group(1)}
                    
        return {"takeaway": "Error extracting content."}

    except Exception as e:
        logger.error(f"Error processing chunk: {str(e)}")
        return {
            "takeaway": "Error occurred during content processing."
        }

@cache_result
def _combine_summaries(summaries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Combine chunk summaries with improved error handling and caching."""
    # Define combined_text at function scope to avoid unbound errors
    combined_text = ""
    
    # Quick returns for edge cases
    if not summaries:
        return {"takeaway": "No content available to summarize."}

    if len(summaries) == 1:
        return summaries[0]

    try:
        # Process the summaries into combined text - more efficiently
        valid_takeaways = [s.get("takeaway", "") for s in summaries if s and "takeaway" in s]
        if valid_takeaways:
            combined_text = " ".join(valid_takeaways)
        
        if not combined_text or len(combined_text) < 10:  # Ensure we have meaningful content
            return {"takeaway": "Unable to extract meaningful content from the articles."}

        prompt = (
            "Combine these takeaways into a single business-focused takeaway following these STRICT RULES:\n\n" +
            "1. Write EXACTLY 3-4 impactful sentences in a single paragraph (70-90 words total)\n" +
            "2. ALWAYS include specific company names from the original takeaways\n" +
            "3. MUST include the most significant REAL quantitative data (revenue, user counts, percentages)\n" +
            "4. NEVER fabricate numbers - use ONLY statistics mentioned in the source takeaways\n" +
            "5. Prioritize measurable ROI, cost savings, or performance improvements\n" +
            "6. Clearly explain HOW companies are using AI technology and WHY it matters\n" +
            "7. Format all numbers consistently with proper commas and spacing\n" +
            "8. Use plain, accessible language that executives can understand\n" +
            "9. Focus on strategic business impact and competitive advantage\n" +
            "10. Maintain professional tone - NO promotional language or vague claims\n\n" +
            "Respond in JSON format: {\"takeaway\": \"combined takeaway\"}\n\n" +
            f"Takeaways to combine: {combined_text[:50000]}"  # Limit text size
        )

        try:
            # Use an explicit model with better error handling
            response = client.chat.completions.create(
                model="gpt-4o-mini",  # Using gpt-4o-mini for balance of speed and quality
                messages=[
                    {"role": "system", "content": "You are a JSON generator. You must return ONLY valid, complete JSON in format {\"takeaway\": \"text\"}. Ensure all quotes are properly escaped and closed."},
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=2000,
                response_format={"type": "json_object"},
                timeout=30
            )
        except Exception as api_error:
            logger.error(f"API error during summary combination: {str(api_error)}")
            # Return the first summary as fallback on API error
            if summaries and "takeaway" in summaries[0]:
                return summaries[0]
            return {"takeaway": "Unable to combine summaries due to API limitations."}

        if not response or not response.choices or not response.choices[0].message:
            logger.warning("Empty response received from API during combination")
            return {"takeaway": "Error: Empty response from AI"}
            
        content = response.choices[0].message.content
        if content:
            content = content.strip()
            try:
                return json.loads(content)
            except json.JSONDecodeError as json_err:
                logger.warning(f"JSON decode error in combine: {json_err} - Content: {content[:100]}...")
                
                # Progressive fallback with better patterns
                # First try a more precise pattern for quoted takeaway
                takeaway_match = re.search(r'"takeaway"\s*:\s*"((?:[^"\\]|\\.)*)(?:"|\Z)', content)
                if takeaway_match:
                    return {"takeaway": takeaway_match.group(1)}
                    
                # Try an alternate pattern that just gets everything between the quotes
                takeaway_match = re.search(r'"takeaway"\s*:\s*"([^"]*)', content)
                if takeaway_match:
                    return {"takeaway": takeaway_match.group(1)}
                    
                # As a last resort, just try to extract any text after the takeaway key
                takeaway_match = re.search(r'"takeaway"\s*:\s*["\']?([^"}\']+)', content)
                if takeaway_match:
                    return {"takeaway": takeaway_match.group(1)}
        
        # If we get here, use the combined text as fallback (combined_text is always initialized above)
        return {"takeaway": combined_text[:2000] if combined_text else "Error processing content"}

    except Exception as e:
        logger.error(f"Error combining summaries: {str(e)}")
        # Return a meaningful fallback even in case of errors
        if summaries and len(summaries) > 0 and "takeaway" in summaries[0]:
            return summaries[0]  # Return the first summary if available
        return {"takeaway": "Error processing content"}

def summarize_article(content: str) -> Dict[str, Any]:
    """Generate a takeaway for an article with improved efficiency and error handling."""
    try:
        # Quick validation of content
        if not content or len(content) < 100:
            return {
                "takeaway": "Article content is too short or empty."
            }

        # Normalize content to improve processing
        content = re.sub(r'\s+', ' ', content.strip())
        
        # Generate a unique identifier for the article content for caching
        content_hash = hashlib.md5(content[:10000].encode()).hexdigest()
        cache_key = f"article_summary:{content_hash}"
        
        # Check if we already have this article cached
        if cache_key in _cache:
            timestamp, result = _cache[cache_key]
            # Use cache if less than 24 hours old
            if time.time() - timestamp < 86400:  # 24 hours in seconds
                logger.info(f"Using cached article summary")
                return result
        
        # Split content into manageable chunks
        chunks = split_into_chunks(content, max_chunk_size=40000)

        if not chunks:
            return {
                "takeaway": "Unable to process content."
            }

        # Process chunks in parallel if there are multiple chunks
        chunk_summaries = []
        for i, chunk in enumerate(chunks):
            chunk_tokens = len(chunk) // 3
            logger.info(f"Processing chunk {i+1}/{len(chunks)} (~{chunk_tokens} tokens)")

            if chunk_tokens > 40000:
                logger.warning(f"Chunk {i+1} too large ({chunk_tokens} tokens), truncating")
                truncated_chunk = chunk[:120000]
                summary = _process_chunk(truncated_chunk)
            else:
                summary = _process_chunk(chunk)

            if summary:
                chunk_summaries.append(summary)

        if not chunk_summaries:
            return {
                "takeaway": "Content could not be processed properly."
            }

        # Combine summaries - already uses caching via the decorator
        combined = _combine_summaries(chunk_summaries)
        result = combined if combined else {
            "takeaway": "Error combining article summaries."
        }
        
        # Cache the final result
        _cache[cache_key] = (time.time(), result)
        
        return result

    except Exception as e:
        logger.error(f"Error summarizing article: {str(e)}")
        return {
            "takeaway": "Unable to analyze content at this time."
        }
