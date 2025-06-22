
import os
import json
import logging
import functools
import hashlib
import re
import time
from typing import Any, Dict, List, Optional

from openai import OpenAI
from utils import config_manager

# Configure logging
logger = logging.getLogger(__name__)


# Lazily initialized OpenAI client
_client = None

def _get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    return _client

# Simple in-memory cache for API responses
# Simple in-memory cache for API responses
_cache = {}

# Cached categorization framework and mtime
_cached_framework: Optional[str] = None
_cached_framework_mtime: float = 0.0

# Cached rubric and file modification timestamp
_cached_rubric: Optional[str] = None
_cached_rubric_mtime: float = 0.0

def _get_takeaway_rubric() -> str:
    """Retrieve the current takeaway rubric using a cached config value."""
    global _cached_rubric, _cached_rubric_mtime

    try:
        mtime = os.path.getmtime(config_manager.CONFIG_PATH)
    except OSError:
        mtime = 0.0

    if _cached_rubric is None or mtime != _cached_rubric_mtime:
        cfg = config_manager.load_config()
        _cached_rubric = cfg.get(
            "takeaway_rubric",
            config_manager.DEFAULT_CONFIG["takeaway_rubric"],
        )
        _cached_rubric_mtime = mtime

    return _cached_rubric


def get_categorization_framework_text() -> str:
    """Load the categorization framework text from data/criteria."""
    global _cached_framework, _cached_framework_mtime
    framework_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                  "data", "criteria", "categorization_framework.txt")

    try:
        mtime = os.path.getmtime(framework_path)
    except OSError:
        mtime = 0.0

    if _cached_framework is None or mtime != _cached_framework_mtime:
        try:
            with open(framework_path, "r", encoding="utf-8") as f:
                _cached_framework = f.read()
        except Exception:
            _cached_framework = ""
        _cached_framework_mtime = mtime

    return _cached_framework or "Error: Categorization framework file not found."


CATEGORIZATION_PROMPT_TEMPLATE = """
You are an expert AI analyst specializing in the retail and e-commerce industry, with a focus on Crocs and its competitors.
Your task is to categorize an article based on the provided \"Crocs Articles Categorization Framework\" and provide a brief justification for your choice.

Here is the framework:
--- FRAMEWORK START ---
{categorization_framework}
--- FRAMEWORK END ---

Article Information:
Title: {title}
Content:
{content_snippet}
---

Instructions:
1. Carefully read the article information.
2. Based *only* on the article content and the provided framework, select the ONE most appropriate category from the list (e.g., \"Content & Creative\", \"Business Intelligence (BI)\", etc.).
3. Provide a concise justification (1-2 sentences) explaining *why* you chose that category, referencing specific aspects of the article and how they align with the category definition.
4. If the article clearly discusses a specific competitor mentioned in category 7 (Adidas, Nike, Deckers, Skechers, OOFOS, Puma) regarding their GenAI developments, choose \"Competitor Updates\".
5. If the article doesn't fit neatly into categories 1-5 or 7, use \"Other Applications\".
6. Your output MUST be a JSON object with two keys: \"category\" and \"justification\".

Example Output:
{{
  "category": "Content & Creative",
  "justification": "The article discusses how the brand is using GenAI to create personalized ad copy and visuals at scale, aligning with scalable creative production."
}}

Analyze the article and provide your categorization and justification in the specified JSON format.
"""

def _validate_takeaway(takeaway: str, article_content_sample: str = "") -> Dict[str, Any]:
    """
    Validate takeaway against the rubric and provide refinement instructions.
    The validation will use an LLM to check adherence to each rule.
    """
    rubric = _get_takeaway_rubric()
    word_count = len(takeaway.split())
    sentence_count = len(re.findall(r'[.!?]+', takeaway))

    issues_found = []
    passes_validation = True  # Assume true initially

    # Rule 1: Concise paragraph (3–4 sentences, 70–90 words). Avoid long sentences.
    if not (3 <= sentence_count <= 4):
        issues_found.append(f"Sentence count is {sentence_count}, should be 3-4.")
        passes_validation = False
    if not (70 <= word_count <= 90):
        issues_found.append(f"Word count is {word_count}, should be 70-90 words.")
        passes_validation = False

    # Rule 9: No bullet points. Must be paragraph form.
    if any(bullet in takeaway for bullet in ['*', '-', '•', '1.', 'a)']):
        issues_found.append("Takeaway contains bullet points or list-like formatting.")
        passes_validation = False

    # Rule 11: No overt mention of "the AI leader" or target reader.
    # Making this check case-insensitive and comprehensive.
    leader_patterns = [
        r'\bai leader(s)?\b',
        r'\bretail ai leader(s)?\b', 
        r'\bai leader(s)? in retail\b',
        r'\bfor ai leader(s)?\b',
        r'\bai leadership\b',
        r'\bthe retail leader(s)?\b',
        r'\bretail leader(s)?\b',
        r'\byour target reader\b',
        r'\bthe ai leader\b',
        r'\bleader(s)? in ai\b',
        r'\bleader(s)? concerned with\b',
        r'\binsights for.*leader(s)?\b',
        r'\brelevant.*leader(s)?\b',
        r'\bleader(s)? can leverage\b',
        r'\bthat.*leader(s)? can\b',
        r'\btools that.*leader(s)?\b',
        r'\benabling.*leader(s)?\b',
        r'\bhelping.*leader(s)?\b',
        r'\bassisting.*leader(s)?\b',
        r'\bfor.*leader(s)? to\b',
        r'\bleader(s)? to leverage\b',
        r'\bleader(s)? should\b',
        r'\bleader(s)? need\b',
        r'\bleader(s)? must\b'
    ]
    
    if any(re.search(pattern, takeaway, re.IGNORECASE) for pattern in leader_patterns):
        issues_found.append("Takeaway overtly mentions 'AI leader', 'retail leader', or the target reader.")
        passes_validation = False

    # For more nuanced checks, use an LLM.
    # These include strategic relevance, jargon, tone, grounding in article, etc.
    # This prompt asks the LLM to act as an evaluator.
    # Only call LLM if basic programmatic checks pass or if we want LLM's opinion regardless.
    # For now, let's assume we always want the LLM's qualitative assessment.

    validation_prompt = f"""
    You are an expert evaluator for AI-generated news takeaways for the retail industry.
    Evaluate the following takeaway based *only* on the provided RUBRIC.
    Do not evaluate based on the article content itself, only the takeaway's adherence to the rubric.

    RUBRIC:
    {rubric}

    TAKEAWAY TO EVALUATE:
    "{takeaway}"

    ARTICLE CONTENT SAMPLE (for context if rules require grounding in the article, but evaluate the takeaway itself):
    "{article_content_sample[:1000]}..."

    Perform the following checks based on the RUBRIC:
    1.  **Strategic Relevance**: Does the takeaway highlight strategic relevance for AI leaders in the retail industry? (Rule 2)
    2.  **Specificity**: Does it mention specific company names, AI tools, or platforms if appropriate (i.e., if they were likely in an article that would lead to this takeaway)? (Rule 3)
    3.  **Data Inclusion**: Does it seem to include quantitative/qualitative data appropriately, assuming it was present in the source? (Rule 4)
    4.  **Business Impact**: Does it emphasize business impact and strategic benefits (e.g., content automation, CX improvement)? (Rule 5)
    5.  **Clarity & Jargon**: Is the language clear, digestible, and avoiding technical jargon? (Rule 6)
    6.  **Importance for Retail AI Leaders**: Does it explain why the news matters for AI leaders in retail (implications for e-commerce, logistics, etc.)? (Rule 7)
    7.  **Strategic Perspective**: Does it add a human or strategic perspective (vision, goals, market shifts)? (Rule 8)
    8.  **Vagueness/Visionary Statements**: Is it free of vague or visionary statements, and grounded in plausible specifics? (Rule 10)

    Respond with a JSON object in the following format:
    {{
        "llm_passes_qualitative_checks": true/false,
        "llm_issues_found": ["Specific issue based on the qualitative checks above, e.g., 'Lacks strategic perspective as per Rule 8', 'Uses technical jargon despite Rule 6'"],
        "llm_refinement_suggestions": "Specific, actionable suggestions to fix these qualitative issues."
    }}
    Be very critical and detailed in your issues and suggestions if any are found. If it passes all qualitative checks, llm_issues_found should be an empty list and llm_refinement_suggestions should be an empty string.
    """

    llm_validation_result = {
        "llm_passes_qualitative_checks": True,
        "llm_issues_found": [],
        "llm_refinement_suggestions": ""
    }

    try:
        response = _get_client().chat.completions.create(
            model="gpt-4o", # Ensure this model is appropriate
            messages=[
                {"role": "system", "content": "You are an expert evaluator of AI-generated text, focusing on adherence to specific stylistic and content rules."},
                {"role": "user", "content": validation_prompt}
            ],
            max_completion_tokens=1000, # Adjust as needed
            response_format={"type": "json_object"},
            temperature=0.1, # Low temperature for critical evaluation
            timeout=30 # Increased timeout
        )

        if response and response.choices and response.choices[0].message.content:
            llm_eval = json.loads(response.choices[0].message.content)
            llm_validation_result["llm_passes_qualitative_checks"] = llm_eval.get("llm_passes_qualitative_checks", True)
            llm_validation_result["llm_issues_found"] = llm_eval.get("llm_issues_found", [])
            llm_validation_result["llm_refinement_suggestions"] = llm_eval.get("llm_refinement_suggestions", "")

            if not llm_validation_result["llm_passes_qualitative_checks"]:
                passes_validation = False # Overall validation fails if LLM finds issues
                issues_found.extend(llm_validation_result["llm_issues_found"])
        else:
            logger.warning("LLM validation returned no content or failed.")
            # Decide if this is a hard fail or not. For now, let's say it doesn't invalidate previous checks.
            # issues_found.append("LLM qualitative check could not be performed.")

    except Exception as e:
        logger.error(f"Error during LLM takeaway validation: {str(e)}")
        # issues_found.append(f"LLM qualitative check failed due to error: {str(e)}")
        # Do not change passes_validation here, rely on programmatic checks if LLM fails

    # Construct refinement instructions
    refinement_instructions = "Please address the following issues:\n"
    if (70 <= word_count <= 90) and (3 <= sentence_count <= 4) and not any(bullet in takeaway for bullet in ['*', '-', '•', '1.', 'a)']):
         # If basic structural checks pass, focus on LLM suggestions if any
        if llm_validation_result["llm_refinement_suggestions"]:
             refinement_instructions += llm_validation_result["llm_refinement_suggestions"]
        elif not passes_validation: # Basic checks failed but no LLM suggestions
             for issue in issues_found:
                refinement_instructions += f"- {issue}\n"
        else: # Passed all checks
            refinement_instructions = ""
    else: # Basic structural checks failed
        for issue in issues_found:
            refinement_instructions += f"- {issue}\n"
        if llm_validation_result["llm_refinement_suggestions"]:
             refinement_instructions += "Additionally, consider these qualitative improvements:\n" + llm_validation_result["llm_refinement_suggestions"]


    # If there are no issues at all, refinement_instructions should be empty
    if passes_validation and not llm_validation_result["llm_issues_found"]:
        refinement_instructions = ""
    elif not issues_found and not llm_validation_result["llm_issues_found"]: # handles if passes_validation became false due to LLM but LLM issues are empty (edge case)
        refinement_instructions = ""


    return {
        "passes_validation": passes_validation and llm_validation_result["llm_passes_qualitative_checks"],
        "word_count": word_count,
        "sentence_count": sentence_count,
        "issues_found": issues_found,
        "refinement_instructions": refinement_instructions.strip() if refinement_instructions else "Takeaway meets all primary criteria."
    }

def _refine_takeaway(original_takeaway: str, refinement_instructions: str, original_content: str) -> str:
    """Refine takeaway based on validation feedback."""
    try:
        refinement_prompt = f"""
        Improve this takeaway based on the specific refinement instructions:

        ORIGINAL TAKEAWAY:
        "{original_takeaway}"

        REFINEMENT INSTRUCTIONS:
        {refinement_instructions}

        RUBRIC TO FOLLOW:
        {_get_takeaway_rubric()}

        ORIGINAL CONTENT (for reference):
        {original_content[:5000]}...

        Respond with JSON: {{"takeaway": "improved takeaway here"}}
        """

        response = _get_client().chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an expert at refining business takeaways according to specific instructions and rubrics."},
                {"role": "user", "content": refinement_prompt}
            ],
            max_completion_tokens=1500,
            response_format={"type": "json_object"},
            timeout=25
        )

        if response and response.choices and response.choices[0].message.content:
            result = json.loads(response.choices[0].message.content)
            return result.get("takeaway", original_takeaway)
        
        return original_takeaway

    except Exception as e:
        logger.error(f"Error refining takeaway: {str(e)}")
        return original_takeaway

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
            "Analyze this text and create a business-focused takeaway following these STRICT RULES:\n\n"
            + _get_takeaway_rubric() +
            "\n\nCRITICAL: Never mention 'AI leaders', 'retail leaders', 'leaders', or the target audience directly. "
            "Write as if speaking about general industry implications, not to specific readers.\n\n"
            "Respond with valid JSON only: {\"takeaway\": \"Your concise takeaway here\"}\n"
            "Ensure your JSON has properly closed quotes and braces.\n\n"
            + chunk
        )

        try:
            # Use an explicit model with timeout and retry mechanism
            response = _get_client().chat.completions.create(
                model="gpt-4o",  # Using gpt-4o for better balance of speed and quality
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
                result = json.loads(content)
                takeaway = result.get("takeaway", "")
                
                # Validate the takeaway and refine if needed
                if takeaway:
                    validation = _validate_takeaway(takeaway, chunk) # Pass chunk for context
                    
                    # If validation fails, attempt refinement
                    if not validation.get("passes_validation", True):
                        refinement_instructions = validation.get("refinement_instructions", "")
                        # Only refine if there are actual instructions, not just "Takeaway meets all primary criteria."
                        if refinement_instructions and refinement_instructions != "Takeaway meets all primary criteria.":
                            logger.info(f"Takeaway validation failed, attempting refinement. Issues: {validation.get('issues_found', [])}. Instructions: {refinement_instructions}")
                            refined_takeaway = _refine_takeaway(takeaway, refinement_instructions, chunk)
                            result["takeaway"] = refined_takeaway
                            
                            # Log the refinement
                            logger.info(f"Takeaway refined. Original word count: {validation.get('word_count', 0)}")
                        elif not refinement_instructions:
                             logger.info(f"Takeaway validation failed but no refinement instructions provided. Issues: {validation.get('issues_found', [])}")

                return result
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
            "Combine these takeaways into a single business-focused takeaway following these STRICT RULES:\n\n"
            + _get_takeaway_rubric() +
            "\n\nCRITICAL: Never mention 'AI leaders', 'retail leaders', 'leaders', or the target audience directly. "
            "Write as if describing general industry trends and implications.\n\n"
            "Respond in JSON format: {\"takeaway\": \"combined takeaway\"}\n\n"
            f"Takeaways to combine: {combined_text[:50000]}"
        )

        try:
            # Use an explicit model with better error handling
            response = _get_client().chat.completions.create(
                model="gpt-4o",  # Using gpt-4o for balance of speed and quality
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
                result = json.loads(content)
                takeaway = result.get("takeaway", "")
                
                # Validate the combined takeaway and refine if needed
                if takeaway:
                    validation = _validate_takeaway(takeaway, combined_text) # Pass combined_text for context
                    
                    # If validation fails, attempt refinement
                    if not validation.get("passes_validation", True):
                        refinement_instructions = validation.get("refinement_instructions", "")
                        # Only refine if there are actual instructions
                        if refinement_instructions and refinement_instructions != "Takeaway meets all primary criteria.":
                            logger.info(f"Combined takeaway validation failed, attempting refinement. Issues: {validation.get('issues_found', [])}. Instructions: {refinement_instructions}")
                            refined_takeaway = _refine_takeaway(takeaway, refinement_instructions, combined_text)
                            result["takeaway"] = refined_takeaway
                            
                            # Log the refinement
                            logger.info(f"Combined takeaway refined. Original word count: {validation.get('word_count', 0)}")
                        elif not refinement_instructions:
                            logger.info(f"Combined takeaway validation failed but no refinement instructions provided. Issues: {validation.get('issues_found', [])}")

                return result
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


def categorize_article_content(title: str, content: str) -> Dict[str, str]:
    """Categorize article content using an LLM."""
    framework_text = get_categorization_framework_text()
    if framework_text.startswith("Error"):
        return {"category": "Error", "category_justification": framework_text}

    content_snippet = (content[:3000] + "...") if len(content) > 3000 else content

    prompt = CATEGORIZATION_PROMPT_TEMPLATE.format(
        categorization_framework=framework_text,
        title=title,
        content_snippet=content_snippet,
    )

    try:
        response = _get_client().chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an expert AI analyst."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
            timeout=25,
        )

        if response and response.choices and response.choices[0].message:
            content_json_str = response.choices[0].message.content.strip()
            if content_json_str.startswith("```json"):
                content_json_str = content_json_str[7:]
            if content_json_str.endswith("```"):
                content_json_str = content_json_str[:-3]

            data = json.loads(content_json_str)
            if "category" in data and "justification" in data:
                return {
                    "category": data.get("category", "Uncategorized"),
                    "category_justification": data.get(
                        "justification", "No justification provided."
                    ),
                }
            logger.warning("Categorization output missing keys")
            return {
                "category": "Uncategorized",
                "category_justification": "LLM output format error.",
            }

        logger.warning("No valid response from LLM for categorization")
        return {
            "category": "Uncategorized",
            "category_justification": "LLM response error.",
        }

    except json.JSONDecodeError as e:
        logger.error(f"JSONDecodeError during categorization: {e}")
        return {
            "category": "Uncategorized",
            "category_justification": "Error decoding LLM JSON response.",
        }
    except Exception as e:
        logger.error(f"Error in categorize_article_content: {str(e)}")
        return {
            "category": "Uncategorized",
            "category_justification": f"Categorization error: {str(e)}",
        }
