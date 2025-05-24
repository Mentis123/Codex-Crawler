import re
from agents.base_agent import BaseAgent
from utils.config_manager import load_config


class EvaluationAgent(BaseAgent):
    """Evaluate articles against selection criteria."""

    def __init__(self, config=None):
        cfg = load_config().get("evaluation", {})
        if config:
            cfg.update(config)
        super().__init__(cfg)
        self.companies = cfg.get("companies", [])
        self.tools = cfg.get("tools", [])
        self.retail_terms = cfg.get("retail_terms", [])
        self.roi_pattern = cfg.get(
            "roi_pattern",
            r"\d+%|\$\d+|\d+\s*million|\d+\s*billion|increased|reduced|improved|saved",
        )
        self.promotional_pattern = cfg.get(
            "promotional_pattern",
            r"partner|partnership|sponsor|press release|proud|excited|pleased to|delighted to",
        )
        self.deployment_terms = cfg.get(
            "deployment_terms",
            ["deployed", "implemented", "launched", "in production", "currently using", "rolled out"],
        )
        self.major_platforms = cfg.get(
            "major_platforms",
            ["openai", "microsoft", "google", "amazon", "meta"],
        )

    def evaluate(self, articles):
        evaluated = []
        for article in articles:
            result = self.evaluate_article(article)
            article.update(result)
            evaluated.append(article)
        return evaluated

    def _find_entity(self, text):
        for name in self.companies:
            if re.search(rf"\b{re.escape(name)}\b", text, re.IGNORECASE):
                return name
        # Look for government agencies and other organizations
        match = re.search(r"\b([A-Z][A-Za-z&]+(?:\s+[A-Z][A-Za-z&]+){0,3})\b", text)
        if match:
            return match.group(1)
        return None

    def _find_tool(self, text):
        for name in self.tools:
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

        # Criterion 1: Specific entity using AI tool
        entity = self._find_entity(text)
        tool = self._find_tool(text)
        if entity and tool:
            criteria.append({
                "criteria": "Specific companies using AI tools",
                "status": True,
                "notes": f"{entity} using {tool}"
            })
            score += 1
        else:
            criteria.append({
                "criteria": "Specific companies using AI tools",
                "status": False,
                "notes": "No specific company/tool usage identified"
            })

        # Criterion 2: Third-party GenAI tool
        is_third_party = not re.search(r"own|homegrown|proprietary|in-house|its own", text_lower)
        if tool and is_third_party:
            criteria.append({
                "criteria": "Tool is third-party Gen AI",
                "status": True,
                "notes": f"{tool} is an external, open-source model"
            })
            score += 1
        else:
            criteria.append({
                "criteria": "Tool is third-party Gen AI",
                "status": False,
                "notes": "Using internal/proprietary solution"
            })

        # Criterion 3: Measurable ROI/Business impact
        if re.search(self.roi_pattern, text_lower) and any(term in text_lower for term in ["revenue", "sales", "cost", "efficiency", "productivity"]):
            criteria.append({
                "criteria": "Measurable ROI / Business impact",
                "status": True,
                "notes": "Clear metrics tied to business outcomes"
            })
            score += 1
        else:
            criteria.append({
                "criteria": "Measurable ROI / Business impact",
                "status": False,
                "notes": "No quantifiable business metrics provided"
            })

        # Criterion 4: Retail/E-commerce relevance
        retail_relevance = any(term in text_lower for term in self.retail_terms)
        if retail_relevance:
            criteria.append({
                "criteria": "Relevance to retail priorities",
                "status": True,
                "notes": "Directly relates to retail/e-commerce operations"
            })
            score += 1
        else:
            criteria.append({
                "criteria": "Relevance to retail priorities",
                "status": False,
                "notes": "Not tied to e-commerce, personalization, or retail"
            })

        # Criterion 5: Neutral tone
        promotional = re.search(self.promotional_pattern, text_lower)
        if not promotional:
            criteria.append({
                "criteria": "Neutral tone",
                "status": True,
                "notes": "Focuses on reporting rather than promotion"
            })
            score += 1
        else:
            criteria.append({
                "criteria": "Neutral tone",
                "status": False,
                "notes": "Contains promotional language"
            })

        # Criterion 6: Concrete implementation vs fluff
        if any(t in text_lower for t in self.deployment_terms):
            criteria.append({
                "criteria": "Not customer-service or visionary fluff",
                "status": True,
                "notes": "Descriptive of actual deployment"
            })
            score += 1
        else:
            criteria.append({
                "criteria": "Not customer-service or visionary fluff",
                "status": False,
                "notes": "Focuses on future possibilities/customer service"
            })

        # Criterion 7: Major platform impact
        platform_impact = False
        if any(p in text_lower for p in self.major_platforms) and re.search(r"retail|commerce|shopping|marketplace", text_lower):
            platform_impact = True
            criteria.append({
                "criteria": "OpenAI / Microsoft / Google release impact",
                "status": True,
                "notes": "Major platform update with retail angle"
            })
            score += 1
        else:
            criteria.append({
                "criteria": "OpenAI / Microsoft / Google release impact",
                "status": False,
                "notes": "No significant retail platform impact"
            })

        # Assessment determination based on strict criteria
        if score >= 5 and retail_relevance:
            assessment = "INCLUDE"
        elif score >= 3 and retail_relevance:
            assessment = "OK"
        else:
            assessment = "CUT"

        assessment_score = int((score / 6) * 100)

        return {
            "criteria_results": criteria,
            "assessment": assessment,
            "assessment_score": assessment_score,
        }
