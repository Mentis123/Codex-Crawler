from openai import OpenAI
from llama_index.core import Document
from llama_index.embeddings.openai import OpenAIEmbedding
import os

def calculate_relevance_score(content, criteria):
    """
    Calculates relevance score using LlamaIndex and OpenAI embeddings
    """
    try:
        # Initialize OpenAI embedding model
        embed_model = OpenAIEmbedding()

        # Create documents
        content_doc = Document(text=content)
        criteria_doc = Document(text=criteria)

        # Get embeddings
        content_embedding = embed_model.get_text_embedding(content_doc.text)
        criteria_embedding = embed_model.get_text_embedding(criteria_doc.text)

        # Calculate cosine similarity
        similarity = cosine_similarity(content_embedding, criteria_embedding)

        # Convert similarity to 1-10 score
        score = round(similarity * 10)
        return max(1, min(10, score))

    except Exception as e:
        print(f"Error calculating relevance score: {str(e)}")
        return 1  # Return minimum score on error

def cosine_similarity(vec1, vec2):
    """
    Calculates cosine similarity between two vectors
    """
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = sum(a * a for a in vec1) ** 0.5
    norm2 = sum(b * b for b in vec2) ** 0.5
    return dot_product / (norm1 * norm2)