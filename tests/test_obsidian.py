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


from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_select_relevant_notes_returns_paths(vault, tmp_path):
    notes = [
        {"path": "/vault/心理学/a.md", "title": "认知偏见", "topic": "心理学", "summary": "讲认知偏见"},
        {"path": "/vault/理财/b.md", "title": "指数基金", "topic": "理财", "summary": "讲指数基金投资"},
    ]
    with patch.object(vault, '_select_relevant_notes', wraps=vault._select_relevant_notes):
        with patch('storage.obsidian.llm_client') as mock_llm:
            mock_llm.generate_chat_response = AsyncMock(return_value="1")
            result = await vault._select_relevant_notes("怎么投资？", notes)
    assert result == ["/vault/理财/b.md"]


@pytest.mark.asyncio
async def test_select_relevant_notes_returns_empty_on_no_match(vault):
    notes = [{"path": "/vault/心理学/a.md", "title": "认知偏见", "topic": "心理学", "summary": "..."}]
    with patch('storage.obsidian.llm_client') as mock_llm:
        mock_llm.generate_chat_response = AsyncMock(return_value="无")
        result = await vault._select_relevant_notes("量子物理", notes)
    assert result == []
