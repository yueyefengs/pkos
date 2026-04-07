import pytest
from pathlib import Path
from storage.obsidian import ObsidianStorage


@pytest.fixture
def vault(tmp_path):
    storage = ObsidianStorage.__new__(ObsidianStorage)
    storage.vault_path = tmp_path
    return storage


def test_load_note_summaries_empty_vault(vault):
    result = vault._load_note_summaries()
    assert result == []


def test_load_note_summaries_extracts_fields(vault, tmp_path):
    (tmp_path / "心理学").mkdir()
    (tmp_path / "心理学" / "2026-01-01-测试笔记.md").write_text(
        "---\ntitle: 测试笔记\ntopic: 心理学\n---\n\n## 摘要\n\n这是摘要内容。\n\n## 正文\n\n正文在这里。\n",
        encoding="utf-8"
    )
    result = vault._load_note_summaries()
    assert len(result) == 1
    assert result[0]["title"] == "测试笔记"
    assert result[0]["topic"] == "心理学"
    assert result[0]["summary"] == "这是摘要内容。"
    assert result[0]["path"].endswith(".md")
