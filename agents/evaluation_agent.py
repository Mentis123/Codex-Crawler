import re
from agents.base_agent import BaseAgent


class EvaluationAgent(BaseAgent):
    """Evaluate articles against selection criteria."""

    COMPANIES = [
        "Amazon", "Google", "Microsoft", "OpenAI", "Walmart", "eBay",
        "Target", "Meta", "Apple", "Adobe", "Salesforce", "Nvidia",
        "Anthropic", "Perplexity", "Crocs"
    ]

    TOOLS = [
        "ChatGPT", "Gemini", "Claude", "SageMaker", "Copilot", "DALL-E",
        "Bard", "Midjourney", "Stable Diffusion", "Firefly", "GPT-4",
        "Llama", "Bedrock"
    ]

    def __init__(self, config=None):
        super().__init__(config)

    def evaluate(self, articles):
        evaluated = []
        for article in articles:
            result = self.evaluate_article(article)
            article.update(result)
            evaluated.append(article)
        return evaluated

    def _find_company(self, text):
        for name in self.COMPANIES:
            if re.search(rf"\b{re.escape(name)}\b", text, re.IGNORECASE):
                return name
        match = re.search(r"\b([A-Z][A-Za-z&]+(?:\s+[A-Z][A-Za-z&]+){0,2}\s+(?:Inc|Corp|Corporation|LLC|Ltd|Group|Co))\b", text)
        if match:
            return match.group(1)
        return None

    def _find_tool(self, text):
        for name in self.TOOLS:
            if re.search(rf"\b{re.escape(name)}\b", text, re.IGNORECASE):
                return name
        if re.search(r"generative ai|large language model|llm", text, re.IGNORECASE):
            return "Generative AI"
        return None

    def evaluate_article(self, article):
        text = f"{article.get('title','')} {article.get('content','')} {article.get('takeaway','')}"
        text_lower = text.lower()

        criteria = []
        score = 0

        # Criterion 1: company using AI tool
        company = self._find_company(text)
        tool = self._find_tool(text)
        if company and tool and re.search(r"uses|using|leverages|adopts|deploys|implements|powered by", text_lower):
            criteria.append({"criteria": "Company uses AI tool", "status": True, "notes": f"{company} uses {tool}"})
            score += 1
        else:
            criteria.append({"criteria": "Company uses AI tool", "status": False, "notes": "No real usage found"})

        # Criterion 2: uses market GenAI tool
        if tool and not re.search(r"own|homegrown|proprietary|in-house|its own", text_lower):
            criteria.append({"criteria": "Uses market GenAI tool", "status": True, "notes": tool})
            score += 1
        elif re.search(r"own|homegrown|proprietary|in-house", text_lower):
            criteria.append({"criteria": "Uses market GenAI tool", "status": False, "notes": "Building own platform"})
        else:
            criteria.append({"criteria": "Uses market GenAI tool", "status": False, "notes": "No GenAI tool mentioned"})

        # Criterion 3: measurable ROI or impact
        if re.search(r"\d+%|\$\d|roi|return on investment|savings|increase|decrease|growth|improvement|cost savings|reduced", text_lower):
            criteria.append({"criteria": "Measurable ROI", "status": True, "notes": "Impact metrics present"})
            score += 1
        else:
            criteria.append({"criteria": "Measurable ROI", "status": False, "notes": "No clear metrics"})

        # Criterion 4: relevant to focus areas
        if re.search(r"ecommerce|retail|personalization|recommendation|shopping|supply chain|logistics|business intelligence|enterprise chat|creative|content|merchandising|inventory", text_lower):
            criteria.append({"criteria": "Relevant to focus", "status": True, "notes": "Matches focus keywords"})
            score += 1
        else:
            criteria.append({"criteria": "Relevant to focus", "status": False, "notes": "Not aligned"})

        # Criterion 5: neutral, not promotional
        if re.search(r"partner|partnership|sponsor|press release|promotion", text_lower):
            criteria.append({"criteria": "Neutral tone", "status": False, "notes": "Promotional/partnership"})
        else:
            criteria.append({"criteria": "Neutral tone", "status": True, "notes": "Neutral"})
            score += 1

        # Criterion 6: exclude customer service or visionary
        if re.search(r"customer service|customer support|call center|visionary|future of", text_lower):
            criteria.append({"criteria": "Exclude support/visionary", "status": False, "notes": "Service or visionary focus"})
        else:
            criteria.append({"criteria": "Exclude support/visionary", "status": True, "notes": "Meets requirement"})
            score += 1

        # Criterion 7: major platform update
        if re.search(r"(openai|microsoft|google|amazon|walmart|e-?bay).*?(release|update|launch|announce|rollout)", text_lower):
            criteria.append({"criteria": "Major platform update", "status": True, "notes": "Update detected"})
            major_update = True
        else:
            criteria.append({"criteria": "Major platform update", "status": False, "notes": "No major update"})
            major_update = False

        # Assessment determination
        if major_update:
            assessment = "INCLUDE"
        elif score >= 4:
            assessment = "INCLUDE"
        elif score >= 3:
            assessment = "OK"
        else:
            assessment = "CUT"

        assessment_score = int((score / 6) * 100)

        return {
            "criteria_results": criteria,
            "assessment": assessment,
            "assessment_score": assessment_score,
        }
