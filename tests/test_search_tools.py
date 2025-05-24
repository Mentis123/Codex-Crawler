import unittest
from unittest.mock import patch, Mock
from datetime import datetime
import os
import sys
import types

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Stub external dependencies
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
sys.modules.setdefault('trafilatura', types.ModuleType('trafilatura'))

import utils.search_tools as st


class TestSearchTools(unittest.TestCase):
    @patch('utils.search_tools.requests.get')
    def test_search_arxiv(self, mock_get):
        xml = '''<feed xmlns="http://www.w3.org/2005/Atom">
            <entry>
                <title>AI Paper</title>
                <id>http://arxiv.org/abs/1234</id>
                <published>2024-06-20T00:00:00Z</published>
                <summary>summary text</summary>
            </entry>
        </feed>'''
        mock_resp = Mock(status_code=200, text=xml)
        mock_get.return_value = mock_resp

        cutoff = datetime(2024, 6, 15)
        results = st.search_arxiv(cutoff)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['title'], 'AI Paper')
        self.assertEqual(results[0]['source'], 'arXiv')


if __name__ == '__main__':
    unittest.main()
