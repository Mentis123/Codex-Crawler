import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.default.json")

DEFAULT_CONFIG = {
    "evaluation": {
        "companies": [
            "Amazon", "Google", "Microsoft", "OpenAI", "Walmart", "eBay",
            "Target", "Meta", "Apple", "Adobe", "Salesforce", "Nvidia",
            "Anthropic", "Perplexity", "Crocs"
        ],
        "tools": [
            "ChatGPT", "Gemini", "Claude", "SageMaker", "Copilot", "DALL-E",
            "Bard", "Midjourney", "Stable Diffusion", "Firefly", "GPT-4",
            "Llama", "Bedrock", "Grok"
        ],
        "retail_terms": [
            "ecommerce", "retail", "shopping", "marketplace", "consumer",
            "personalization", "recommendation", "supply chain", "inventory",
            "merchandising", "sales", "customer experience", "revenue"
        ],
        "roi_pattern": "\\d+%|\\$\\d+|\\d+\\s*million|\\d+\\s*billion|increased|reduced|improved|saved",
        "promotional_pattern": "partner|partnership|sponsor|press release|proud|excited|pleased to|delighted to",
        "deployment_terms": ["deployed", "implemented", "launched", "in production", "currently using", "rolled out"],
        "major_platforms": ["openai", "microsoft", "google", "amazon", "meta"]
    },
    "takeaway_rubric": (
        "1. Write a 3-4 sentence focused takeaway (70-90 words)\n"
        "2. Include specific company names mentioned in the article\n"
        "3. Include quantitative data when available (revenue, user counts, percentages)\n"
        "4. Only use statistics from the source text - never fabricate numbers\n"
        "5. Highlight business impacts and strategic benefits of the AI technology\n"
        "6. Use clear language without technical jargon"
    )
}


def archive_default_config():
    """Archive the original default configuration for reset purposes."""
    if not os.path.exists(DEFAULT_CONFIG_PATH):
        with open(DEFAULT_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)


def load_config():
    """Load configuration from disk or return defaults."""
    archive_default_config()
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


def save_config(config: dict):
    """Save configuration to disk."""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def reset_config() -> dict:
    """Restore configuration from archived defaults and return it."""
    if os.path.exists(DEFAULT_CONFIG_PATH):
        with open(DEFAULT_CONFIG_PATH, "r", encoding="utf-8") as f:
            defaults = json.load(f)
    else:
        defaults = DEFAULT_CONFIG.copy()
    save_config(defaults)
    return defaults
