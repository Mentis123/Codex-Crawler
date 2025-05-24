import unittest
from unittest.mock import patch
from datetime import datetime
import os
import sys
import types

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Stub external dependencies not available in the test environment
openai_mod = types.ModuleType('openai')
class _OpenAI:
    def __init__(self, *a, **k):
        pass
openai_mod.OpenAI = _OpenAI
sys.modules.setdefault('openai', openai_mod)
requests_mod = types.ModuleType('requests')
class _Response:
    status_code = 200
    text = ''
    def raise_for_status(self):
        pass
class _ReqEx(Exception):
    pass
requests_mod.get = lambda *a, **k: _Response()
requests_mod.Response = _Response
requests_mod.exceptions = types.SimpleNamespace(RequestException=_ReqEx)
sys.modules.setdefault('requests', requests_mod)

serpapi_mod = types.ModuleType('serpapi')
class _Client:
    def __init__(self, *a, **k):
        pass
    def search(self, *a, **k):
        return {}
serpapi_mod.Client = _Client
sys.modules.setdefault('serpapi', serpapi_mod)

bs4_mod = types.ModuleType('bs4')
bs4_mod.BeautifulSoup = object
sys.modules.setdefault('bs4', bs4_mod)

sys.modules.setdefault('trafilatura', types.ModuleType('trafilatura'))
sys.modules.setdefault('pandas', types.ModuleType('pandas'))
sys.modules.setdefault('pytz', types.ModuleType('pytz'))

llama_index = types.ModuleType('llama_index')
core_mod = types.ModuleType('llama_index.core')
core_mod.Document = object
readers_mod = types.ModuleType('llama_index.readers')
web_mod = types.ModuleType('llama_index.readers.web')
web_mod.BeautifulSoupWebReader = object
sys.modules['llama_index'] = llama_index
sys.modules['llama_index.core'] = core_mod
sys.modules['llama_index.readers'] = readers_mod
sys.modules['llama_index.readers.web'] = web_mod

from agents import search_agent as sa


class TestSearchAgentHelpers(unittest.TestCase):
    @patch('agents.search_agent.ce_extract_metadata')
    def test_extract_metadata(self, mock_meta):
        mock_meta.return_value = {'date': '2024-06-15'}
        cutoff = datetime(2024, 6, 14)
        result = sa.extract_metadata('http://x', cutoff)
        self.assertIsNotNone(result)
        self.assertEqual(result['date'].date(), datetime(2024, 6, 15).date())

    @patch('agents.search_agent.ce_extract_metadata')
    def test_extract_metadata_old_article(self, mock_meta):
        mock_meta.return_value = {'date': '2024-06-01'}
        cutoff = datetime(2024, 6, 10)
        self.assertIsNone(sa.extract_metadata('http://x', cutoff))

    @patch('agents.search_agent.ce_extract_full_content')
    def test_extract_full_content(self, mock_content):
        mock_content.return_value = 'Full text'
        self.assertEqual(sa.extract_full_content('http://x'), 'Full text')

    @patch('agents.search_agent.ai_summarize_article')
    def test_summarize_article(self, mock_sum):
        mock_sum.return_value = {'takeaway': 'summary'}
        self.assertEqual(sa.summarize_article('text'), {'takeaway': 'summary'})

    @patch('agents.search_agent.ce_validate_ai_relevance')
    def test_validate_ai_relevance(self, mock_val):
        mock_val.return_value = {'is_relevant': True, 'reason': 'ok'}
        result = sa.validate_ai_relevance({'title': 'AI'})
        self.assertTrue(result['is_relevant'])
        self.assertEqual(result['reason'], 'ok')


if __name__ == '__main__':
    unittest.main()
