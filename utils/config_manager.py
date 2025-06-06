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
    ),
    "full_scan_urls": [
        "https://wwd.com/business-news/technology/",
        "https://sourcingjournal.com/tag/byte-sized-ai/",
        "https://footwearnews.com/c/business/technology/",
        "https://www.retaildive.com/topic/technology/",
        "https://www.retailbrew.com",
        "https://consumergoods.com/artificial-intelligence",
        "https://www.adweek.com/category/emerging-tech/",
        "https://adage.com/live-blog/ai-marketing-updates-chatgpt-dall-e-2-and-other-tools",
        "https://ppc.land/tag/ai/",
        "https://techcrunch.com/category/artificial-intelligence/",
        "https://techcrunch.com/tag/retail/",
        "https://www.digitalcommerce360.com/topic-artificial-intelligence-ecommerce/",
        "https://www.retailtouchpoints.com/",
        "https://chainstoreage.com/technology",
        "https://www.warc.com/feed",
        "https://www.campaignlive.com/us/just-published-on-campaign/martech",
        "https://www.virtasant.com/ai-today",
        "https://aiexpertnetwork.notion.site/AI-Transformation-Case-Studies-779878d924fa466186071b7939d7599a",
        "https://www.bain.com/insights/?filters=offerings(2007762)",
        "https://retailwire.com/tag/artificial-intelligence/",
        "https://www.wsj.com/tech/ai",
        "https://sloanreview.mit.edu/topic/ai-machine-learning/",
        "https://hbr.org/topic/subject/generative-ai",
        "https://hbr.org/topic/subject/ai-and-machine-learning",
        "https://www.footwearinnovationnews.com/",
        "https://venturebeat.com/category/ai/",
        "https://www.google.co.in/alerts#1:7",
        "https://www.retailcustomerexperience.com/topics/omnichannel-retail/",
        "http://www.diginomica.com/",
        "https://www.technologyreview.com/topic/artificial-intelligence/",
        "https://www.wired.com/tag/artificial-intelligence/"
    ],
    "test_scan_urls": [
        "https://techcrunch.com/category/artificial-intelligence/"
    ]
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
