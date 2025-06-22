
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.content_extractor import extract_full_content
from utils.ai_analyzer import summarize_article

def test_takeaway_generation():
    """Test the current takeaway generation on a specific URL"""
    url = "https://www.virtasant.com/ai-today/ai-operational-efficiency-private-equity"
    
    print(f"Testing takeaway generation for: {url}")
    print("=" * 80)
    
    # Extract content
    print("1. Extracting content...")
    content = extract_full_content(url)
    
    if not content:
        print("Failed to extract content from URL")
        return
    
    print(f"Content extracted successfully ({len(content)} characters)")
    print("\nFirst 500 characters of content:")
    print("-" * 50)
    print(content[:500] + "...")
    print("-" * 50)
    
    # Generate takeaway
    print("\n2. Generating takeaway using current system...")
    try:
        analysis = summarize_article(content)
        takeaway = analysis.get('takeaway', 'No takeaway generated')
        
        print("\nGENERATED TAKEAWAY:")
        print("=" * 80)
        print(takeaway)
        print("=" * 80)
        
        # Show word and sentence count
        word_count = len(takeaway.split())
        sentence_count = len([s for s in takeaway.split('.') if s.strip()])
        
        print(f"\nTakeaway Statistics:")
        print(f"- Word count: {word_count}")
        print(f"- Sentence count: {sentence_count}")
        print(f"- Character count: {len(takeaway)}")
        
        # Check if it meets the rubric criteria
        print(f"\nRubric Compliance:")
        print(f"- Word count (70-90): {'✓' if 70 <= word_count <= 90 else '✗'}")
        print(f"- Sentence count (3-4): {'✓' if 3 <= sentence_count <= 4 else '✗'}")
        print(f"- No bullet points: {'✓' if not any(bullet in takeaway for bullet in ['*', '-', '•', '1.', 'a)']) else '✗'}")
        
    except Exception as e:
        print(f"Error generating takeaway: {str(e)}")

if __name__ == "__main__":
    test_takeaway_generation()
