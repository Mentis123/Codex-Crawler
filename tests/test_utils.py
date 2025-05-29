import sys, types
sys.path.insert(0, "/tmp")
import openai_stub

# Stub external modules not installed in this environment
sys.modules["openai"] = types.SimpleNamespace(OpenAI=openai_stub.Dummy)
sys.modules.setdefault("yaml", types.SimpleNamespace(safe_load=lambda f: {}))
sys.modules.setdefault("trafilatura", types.SimpleNamespace(fetch_url=lambda *a, **k: None, extract=lambda *a, **k: None))
sys.modules.setdefault("pytz", types.SimpleNamespace(UTC=types.SimpleNamespace(localize=lambda x: x)))
sys.modules.setdefault("pandas", types.SimpleNamespace(read_csv=lambda *a, **k: None, DataFrame=object))
sys.modules.setdefault("bs4", types.SimpleNamespace(BeautifulSoup=object))
sys.modules.setdefault("requests", types.SimpleNamespace(get=lambda *a, **k: None, Response=type("Response", (), {})))

from datetime import datetime
import json
import os
import sqlite3
import time

import pytest

from utils import common, config_manager, content_extractor, ai_analyzer, db_manager


def test_format_date():
    dt = datetime(2024, 1, 2)
    assert common.format_date(dt) == "2024-01-02"


def test_validate_timeframe():
    cutoff = datetime(2024, 1, 1)
    assert common.validate_timeframe("2024-01-02", cutoff)
    assert not common.validate_timeframe("2023-12-31", cutoff)
    assert not common.validate_timeframe("bad-date", cutoff)


def test_config_manager_load_save(tmp_path, monkeypatch):
    tmp_file = tmp_path / "config.json"
    default_file = tmp_path / "config.default.json"
    monkeypatch.setattr(config_manager, "DEFAULT_CONFIG_PATH", str(default_file))
    sample = {"a": 1}
    tmp_file.write_text(json.dumps(sample))
    monkeypatch.setattr(config_manager, "CONFIG_PATH", str(tmp_file))
    loaded = config_manager.load_config()
    assert loaded == sample

    sample2 = {"b": 2}
    config_manager.save_config(sample2)
    assert json.loads(tmp_file.read_text()) == sample2


def test_config_manager_reset(tmp_path, monkeypatch):
    cfg_file = tmp_path / "config.json"
    default_file = tmp_path / "config.default.json"
    monkeypatch.setattr(config_manager, "CONFIG_PATH", str(cfg_file))
    monkeypatch.setattr(config_manager, "DEFAULT_CONFIG_PATH", str(default_file))

    monkeypatch.setattr(config_manager, "DEFAULT_CONFIG", {"orig": 1})
    config_manager.archive_default_config()
    config_manager.save_config({"changed": 2})
    assert json.loads(cfg_file.read_text()) == {"changed": 2}

    config_manager.reset_config()
    assert json.loads(cfg_file.read_text()) == {"orig": 1}


def test_clean_article_title():
    assert content_extractor.clean_article_title("Permalink to Test") == "Test"
    assert content_extractor.clean_article_title("Normal Title") == "Normal Title"


def test_is_specific_article():
    meta = {"title": "My Article", "url": "https://example.com/a"}
    assert content_extractor.is_specific_article(meta)

    meta = {"title": "About", "url": "https://example.com/about"}
    assert not content_extractor.is_specific_article(meta)

    meta = {"title": "AI", "url": "https://example.com/category/artificial-intelligence/"}
    assert not content_extractor.is_specific_article(meta)

    meta = {"title": "AI", "url": "https://example.com/tag/ai/"}
    assert not content_extractor.is_specific_article(meta)


def test_split_into_chunks():
    text = "word " * 10000
    chunks = ai_analyzer.split_into_chunks(text, max_chunk_size=1000)
    assert len(chunks) > 1
    assert all(len(c) <= 3000 for c in chunks)


def test_db_manager_in_memory(monkeypatch):
    def dummy_init(self):
        self.conn = sqlite3.connect(":memory:")
        self.local = types.SimpleNamespace(conn=self.conn)
        self.create_tables()

    monkeypatch.setattr(db_manager.DBManager, "__init__", dummy_init, raising=False)
    db = db_manager.DBManager()
    article = {
        "url": "http://example.com",
        "title": "Title",
        "date": "2024-01-01",
        "content": "c",
        "summary": "s",
        "ai_validation": "v",
    }
    db.save_article(article)
    rows = db.get_articles()
    assert len(rows) == 1
    assert rows[0]["url"] == "http://example.com"


def test_get_takeaway_rubric_reload(tmp_path, monkeypatch):
    cfg_file = tmp_path / "config.json"
    default_file = tmp_path / "config.default.json"
    monkeypatch.setattr(config_manager, "CONFIG_PATH", str(cfg_file))
    monkeypatch.setattr(config_manager, "DEFAULT_CONFIG_PATH", str(default_file))

    content = {"takeaway_rubric": "orig"}
    cfg_file.write_text(json.dumps(content))
    default_file.write_text(json.dumps(content))

    monkeypatch.setattr(ai_analyzer, "_cached_rubric", None, raising=False)
    monkeypatch.setattr(ai_analyzer, "_cached_rubric_mtime", 0.0, raising=False)

    first = ai_analyzer._get_takeaway_rubric()
    assert first == "orig"

    time.sleep(1)
    cfg_file.write_text(json.dumps({"takeaway_rubric": "updated"}))
    os.utime(cfg_file, None)
    updated = ai_analyzer._get_takeaway_rubric()
    assert updated == "updated"
