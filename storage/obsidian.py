"""
Obsidian 知识库存储
将处理完成的视频内容以 Markdown 格式写入 Obsidian Vault
"""
import re
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional
from models.task import Task
from processors.llm_client import llm_client
from config.settings import settings
from config.logger import logger

SUMMARY_PROMPT = """请为以下视频内容生成一段简洁的摘要（200字以内）。

视频标题：{title}

内容：
{content}

要求：
1. 提炼核心观点和主要内容
2. 语言简洁清晰
3. 不超过200字"""

TOPIC_CATEGORIES = [
    "工作",
    "理财",
    "经济学",
    "科学自然",
    "教育",
    "生命质量",
    "文化娱乐",
    "历史",
    "心理学",
    "哲学",
    "时事政治",
    "社会学",
    "人物",
    "其他",
]

TOPIC_PROMPT = """请判断以下视频内容属于哪个主题分类。

可选分类：{categories}

视频标题：{title}

内容摘要：
{content}

只回答分类名称，不要有其他文字。"""


class ObsidianStorage:
    def __init__(self):
        vault = getattr(settings, "obsidian_vault_path", None)
        self.vault_path: Optional[Path] = Path(vault) if vault else None

    def _is_enabled(self) -> bool:
        return self.vault_path is not None

    def _sanitize_filename(self, title: str) -> str:
        """去除文件名非法字符，限制长度"""
        safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", title)
        safe = safe.strip(". ")
        return safe[:50] or "untitled"

    async def _generate_summary(self, content: str, title: str) -> str:
        """调用 LLM 生成摘要"""
        prompt = SUMMARY_PROMPT.format(title=title, content=content[:3000])
        try:
            return await llm_client.generate_chat_response(prompt)
        except Exception as e:
            logger.error(f"[Obsidian] Failed to generate summary: {e}")
            return ""

    async def _classify_topic(self, content: str, title: str) -> str:
        """调用 LLM 判断主题分类，返回预设列表中的一项"""
        prompt = TOPIC_PROMPT.format(
            categories="、".join(TOPIC_CATEGORIES),
            title=title,
            content=content[:1500],
        )
        try:
            result = (await llm_client.generate_chat_response(prompt)).strip()
            # 确保返回值在预设列表中，否则归入「其他」
            return result if result in TOPIC_CATEGORIES else "其他"
        except Exception as e:
            logger.error(f"[Obsidian] Failed to classify topic: {e}")
            return "其他"

    def _load_note_summaries(self) -> list[dict]:
        """扫描 vault 所有 .md 文件，提取 frontmatter + 摘要段"""
        notes = []
        for md_file in self.vault_path.rglob("*.md"):
            try:
                text = md_file.read_text(encoding="utf-8")
                title = md_file.stem
                topic = md_file.parent.name
                fm_match = re.search(r"^---\n(.*?)\n---", text, re.DOTALL)
                if fm_match:
                    for line in fm_match.group(1).splitlines():
                        if line.startswith("title:"):
                            title = line[6:].strip()
                        elif line.startswith("topic:"):
                            topic = line[6:].strip()
                summary = ""
                summary_match = re.search(r"## 摘要\n\n(.*?)(?=\n## |\Z)", text, re.DOTALL)
                if summary_match:
                    summary = summary_match.group(1).strip()[:500]
                notes.append({"path": str(md_file), "title": title, "topic": topic, "summary": summary})
            except Exception as e:
                logger.warning(f"[Obsidian] Failed to read {md_file}: {e}")
        return notes

    async def _select_relevant_notes(self, question: str, notes: list[dict]) -> list[str]:
        """LLM 从摘要列表中选出与问题相关的文件路径（最多3个）"""
        notes_text = "\n\n".join(
            f"[{i}] 路径: {n['path']}\n标题: {n['title']}\n主题: {n['topic']}\n摘要: {n['summary']}"
            for i, n in enumerate(notes)
        )
        prompt = (
            f"用户问题：{question}\n\n"
            f"以下是知识库中的笔记摘要列表：\n\n{notes_text}\n\n"
            f"请选出最相关的笔记编号（最多3个），只回答编号，用逗号分隔。如果没有相关笔记，回答'无'。\n"
            f"例如：0,2"
        )
        try:
            result = (await llm_client.generate_chat_response(prompt)).strip()
            if result == "无":
                return []
            indices = [int(x.strip()) for x in result.split(",") if x.strip().isdigit()]
            return [notes[i]["path"] for i in indices if i < len(notes)]
        except Exception as e:
            logger.error(f"[Obsidian] Failed to select relevant notes: {e}")
            return []

    async def _synthesize_answer(self, question: str, paths: list[str], texts: list[str]) -> str:
        """LLM 基于相关文件全文综合回答，附引用来源"""
        sources_text = "\n\n---\n\n".join(
            f"来源：{Path(p).name}\n\n{t[:5000]}"
            for p, t in zip(paths, texts)
        )
        prompt = (
            f"请基于以下知识库笔记回答用户的问题。\n\n"
            f"用户问题：{question}\n\n"
            f"知识库内容：\n{sources_text}\n\n"
            f"要求：\n"
            f"1. 基于笔记内容直接回答，不添加笔记中没有的事实\n"
            f"2. 在回答末尾注明引用来源（文件名）\n"
            f"3. 如果笔记内容不足以回答，诚实说明"
        )
        try:
            return await llm_client.generate_chat_response(prompt)
        except Exception as e:
            logger.error(f"[Obsidian] Failed to synthesize answer: {e}")
            return "回答生成失败，请稍后重试。"

    async def save_note(self, task: Task) -> bool:
        """
        将任务内容保存为 Obsidian Markdown 笔记

        Args:
            task: 已完成的 Task 对象（需包含 content 字段）

        Returns:
            bool: 是否成功写入
        """
        if not self._is_enabled():
            return False
        if not task.content:
            logger.warning(f"[Obsidian] Task {task.task_id} has no content, skipping")
            return False

        try:
            # 并行生成摘要和主题分类
            summary, topic = await asyncio.gather(
                self._generate_summary(task.content, task.title or ""),
                self._classify_topic(task.content, task.title or ""),
            )

            # 按主题分子目录
            note_dir = self.vault_path / topic
            note_dir.mkdir(parents=True, exist_ok=True)

            # 构建文件名：日期-标题.md
            date_str = (task.completed_at or datetime.now()).strftime("%Y-%m-%d")
            safe_title = self._sanitize_filename(task.title or task.task_id)
            filepath = note_dir / f"{date_str}-{safe_title}.md"

            # 文件名冲突时加 task_id 后缀
            if filepath.exists():
                filepath = note_dir / f"{date_str}-{safe_title}-{task.task_id[:6]}.md"

            # 构建笔记内容
            created_str = (task.completed_at or datetime.now()).strftime("%Y-%m-%dT%H:%M:%S")
            note = (
                f"---\n"
                f"title: {task.title or task.task_id}\n"
                f"source: {task.video_url}\n"
                f"platform: {task.platform or 'unknown'}\n"
                f"topic: {topic}\n"
                f"created: {created_str}\n"
                f"task_id: {task.task_id}\n"
                f"---\n\n"
                f"## 摘要\n\n"
                f"{summary}\n\n"
                f"## 正文\n\n"
                f"{task.content}\n"
            )

            filepath.write_text(note, encoding="utf-8")
            logger.info(f"[Obsidian] Note saved: {filepath} (topic={topic})")
            return True

        except Exception as e:
            logger.error(f"[Obsidian] Failed to save note for task {task.task_id}: {e}")
            return False


obsidian_storage = ObsidianStorage()
