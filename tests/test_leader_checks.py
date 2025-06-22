import types, sys
sys.modules['openai'] = types.SimpleNamespace(OpenAI=types.SimpleNamespace())

from utils import ai_analyzer


def test_validate_takeaway_leader_patterns():
    text = "This update is crucial for AI executives in retail to leverage."
    result = ai_analyzer._validate_takeaway(text)
    assert not result["passes_validation"]
    assert any('leader' in issue.lower() or 'target' in issue.lower() for issue in result["issues_found"])

def test_rubric_hash_changes(monkeypatch):
    monkeypatch.setattr(ai_analyzer, "_cached_rubric", "AAA", raising=False)
    monkeypatch.setattr(ai_analyzer, "_cached_rubric_mtime", 0.0, raising=False)
    hash1 = ai_analyzer._get_rubric_hash()
    monkeypatch.setattr(ai_analyzer, "_cached_rubric", "BBB", raising=False)
    hash2 = ai_analyzer._get_rubric_hash()
    assert hash1 != hash2
