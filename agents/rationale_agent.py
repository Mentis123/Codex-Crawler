from openai import OpenAI
import os

class RationaleAgent:
    def __init__(self):
        # the newest OpenAI model is "gpt-4o" which was released May 13, 2024
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.model = "o3-mini"

    def generate_rationales(self, articles, criteria_text):
        """
        Generates two-sentence rationales for articles based on evaluation criteria
        """
        articles_with_rationales = []

        for article in articles:
            rationale = self._generate_single_rationale(article, criteria_text)
            article['rationale'] = rationale
            articles_with_rationales.append(article)

        return articles_with_rationales

    def _generate_single_rationale(self, article, criteria_text):
        """
        Generates a rationale for a single article considering the evaluation criteria
        """
        prompt = f"""
        Generate a two-sentence rationale for the following AI news article,
        specifically addressing how it relates to these evaluation criteria:

        Criteria:
        {criteria_text[:500]}  # Limit criteria length for API

        Sentence 1: Summarize the key AI news in a business context.
        Sentence 2: Explain the significance and potential impact, specifically
        relating to the evaluation criteria.

        Keep the total word count between 30-40 words.

        Article Title: {article['title']}
        Content: {article['content'][:1000]}  # Limit content length for API
        """

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100,
            temperature=0.7
        )

        return response.choices[0].message.content.strip()