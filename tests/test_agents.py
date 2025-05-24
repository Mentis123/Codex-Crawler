import sys, types
sys.modules["openai"] = types.SimpleNamespace(OpenAI=types.SimpleNamespace())
import builtins
from datetime import datetime, timedelta

import pytest

from agents.base_agent import BaseAgent
from agents.analyzer_agent import AnalyzerAgent

class DummyAgent(BaseAgent):
    def process(self, input_data):
        return input_data


def test_base_agent_report_status():
    agent = DummyAgent()
    status = agent.report_status()
    assert status['agent'] == 'DummyAgent'
    assert 'elapsed_time' in status
    assert status['status'] == 'Active'


def test_analyzer_split_into_chunks():
    agent = AnalyzerAgent(config={})
    long_text = "Sentence. " * 6000  # large content
    chunks = agent._split_into_chunks(long_text, max_chunk_size=1000)
    assert len(chunks) > 1
    assert all(len(chunk) <= 1200 for chunk in chunks)
    reconstructed = ' '.join(chunks)
    assert reconstructed.replace(' ', '')[:1000] in long_text.replace(' ', '')


def test_analyzer_is_relevant():
    agent = AnalyzerAgent(config={})
    article = {
        'ai_confidence': 45,
        'ai_validation': 'AI term found'
    }
    assert agent.is_relevant(article)

    article = {'ai_confidence': 10, 'ai_validation': ''}
    assert not agent.is_relevant(article)


def test_validate_ai_relevance_title():
    agent = AnalyzerAgent(config={})
    data = {'title': 'New AI breakthrough', 'takeaway': '', 'content': ''}
    result = agent.validate_ai_relevance(data)
    assert result['is_relevant']
    assert 'AI term' in result['reason']
