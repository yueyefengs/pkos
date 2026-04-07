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


@pytest.mark.asyncio
async def test_writeback_does_nothing_when_no_new_knowledge(vault):
    with patch('storage.obsidian.llm_client') as mock_llm:
        mock_llm.generate_chat_response = AsyncMock(return_value="无")
        await vault._writeback_knowledge("问题", "回答", [])
    # 没有文件被创建
    assert list(vault.vault_path.rglob("*.md")) == []


@pytest.mark.asyncio
async def test_writeback_appends_to_existing_file(vault, tmp_path):
    (tmp_path / "心理学").mkdir()
    note_path = tmp_path / "心理学" / "2026-01-01-认知偏见.md"
    note_path.write_text("---\ntitle: 认知偏见\n---\n\n## 摘要\n\n摘要\n", encoding="utf-8")

    llm_response = "---\n目标文件标题: 认知偏见\n主题: 心理学\n内容: 新补充的知识\n---"
    with patch('storage.obsidian.llm_client') as mock_llm:
        mock_llm.generate_chat_response = AsyncMock(return_value=llm_response)
        await vault._writeback_knowledge("问题", "回答", [str(note_path)])

    content = note_path.read_text(encoding="utf-8")
    assert "## 补充" in content
    assert "新补充的知识" in content
