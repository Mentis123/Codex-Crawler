from utils.evaluation_tools import calculate_relevance_score
import os

class EvaluationAgent:
    def __init__(self):
        # the newest OpenAI model is "gpt-4o" which was released May 13, 2024
        self.model = "o3-mini"

    def evaluate(self, articles, criteria_text):
        """
        Evaluates articles based on provided criteria
        """
        evaluated_articles = []

        for article in articles:
            # Calculate relevance score using semantic similarity against provided criteria
            relevance_score = calculate_relevance_score(
                article['content'],
                criteria_text
            )

            article['relevance_score'] = relevance_score
            evaluated_articles.append(article)

        # Sort by relevance score
        evaluated_articles.sort(key=lambda x: x['relevance_score'], reverse=True)
        return evaluated_articles