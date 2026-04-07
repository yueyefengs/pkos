"""
对话引擎
基于LLM的对话功能,支持普通模式和学习模式
"""
from telegram import Update
from telegram.ext import ContextTypes
from bot.session_manager import get_session_manager
from bot.telegram_client import get_telegram_client, escape_markdown_v2
from storage.postgres import storage
from processors.llm_client import llm_client
from config.logger import logger
from typing import List, Dict


# 学习模式提示词模板
LEARNING_MODE_PROMPT = """你是一位擅长苏格拉底式教学的导师。你的目标是通过提问和引导,帮助学习者主动思考和理解知识,而不是直接给出答案。

**教学原则:**
1. **友好与耐心** - 使用友好、对话式、非评判的语气
2. **引导思考** - 通过提问引导学习者自己发现答案
3. **逐步深入** - 从简单概念开始,逐步深入复杂内容
4. **验证理解** - 在进入下一个话题前,确认学习者真正理解
5. **鼓励探索** - 鼓励学习者提出自己的问题和想法

**教学方法:**
- 不直接给出答案,而是提出引导性问题
- 当学习者回答错误时,不直接纠正,而是通过问题帮助他们发现问题
- 适时给予肯定和鼓励,保持学习者的积极性
- 根据学习者的反应调整教学节奏

**文章内容:**
{article_content}

**之前的对话:**
{conversation_history}

现在学习者问: {user_question}

请根据苏格拉底式教学方法回应。"""


# 普通模式提示词模板
NORMAL_MODE_PROMPT = """你是一个知识助手,可以帮助用户理解和分析文章内容。

**你的任务:**
1. 基于提供的文章内容回答用户问题
2. 提供清晰、准确、有条理的答案
3. 可以引用文章中的具体内容
4. 如果问题超出文章范围,明确告知用户

**重要限制:**
- 不要添加文章中没有明确表达的事实或结论
- 区分观点和事实
- 所有"扩展"限于提出思考方向,不提供答案

**文章内容:**
{article_content}

**之前的对话:**
{conversation_history}

用户问: {user_question}

请基于文章内容回答。"""


class ConversationEngine:
    """对话引擎"""

    @staticmethod
    def format_history(history: List[Dict[str, str]]) -> str:
        """格式化对话历史"""
        if not history:
            return "(无历史对话)"

        formatted = []
        for msg in history[-5:]:  # 只取最近5轮
            role = "用户" if msg["role"] == "user" else "助手"
            formatted.append(f"{role}: {msg['content']}")

        return "\n".join(formatted)

    @staticmethod
    async def generate_response(
        user_question: str,
        article_content: str,
        mode: str,
        history: List[Dict[str, str]]
    ) -> str:
        """
        生成AI回复

        Args:
            user_question: 用户问题
            article_content: 文章内容
            mode: 对话模式 ("normal" 或 "learning")
            history: 对话历史

        Returns:
            str: AI回复
        """
        # 格式化历史
        history_str = ConversationEngine.format_history(history)

        # 选择提示词模板
        if mode == "learning":
            prompt = LEARNING_MODE_PROMPT.format(
                article_content=article_content[:4000],  # 限制长度
                conversation_history=history_str,
                user_question=user_question
            )
        else:
            prompt = NORMAL_MODE_PROMPT.format(
                article_content=article_content[:4000],  # 限制长度
                conversation_history=history_str,
                user_question=user_question
            )

        # 调用LLM
        try:
            response = await llm_client.generate_chat_response(prompt)
            return response
        except Exception as e:
            logger.error(f"Failed to generate response: {e}")
            return f"抱歉,生成回复时出错: {str(e)}"

    @staticmethod
    async def handle_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        处理对话消息

        流程:
        1. 获取用户工作区和模式
        2. 获取文章内容
        3. 获取对话历史
        4. 生成AI回复
        5. 保存对话历史
        6. 更新学习进度(如果在学习模式)
        """
        user_id = str(update.effective_user.id)
        chat_id = str(update.effective_chat.id)
        user_message = update.message.text
        client = get_telegram_client()
        session = get_session_manager()

        try:
            # 1. 获取工作区和模式
            await session.connect()
            workspace_ids = await session.get_workspace(user_id)
            mode = await session.get_mode(user_id)
            history = await session.get_history(user_id, limit=10)

            if not workspace_ids:
                await session.disconnect()
                await client.send_message(
                    chat_id,
                    "📭 工作区为空,无法进行对话\n\n使用 `/chat [任务ID]` 激活文章"
                )
                return

            # 2. 获取文章内容(支持多篇文章,先用第一篇)
            await storage.connect()
            tasks = await storage.get_recent_tasks(limit=100)
            await storage.disconnect()

            active_tasks = [t for t in tasks if t.id in workspace_ids]
            if not active_tasks:
                await session.disconnect()
                await client.send_message(
                    chat_id,
                    "❌ 找不到激活的文章\n\n请重新使用 `/chat [任务ID]` 激活"
                )
                return

            # 使用第一篇文章
            article = active_tasks[0]
            if not article.content:
                await session.disconnect()
                await client.send_message(
                    chat_id,
                    "❌ 文章内容为空,无法进行对话"
                )
                return

            # 3. 生成AI回复
            response = await ConversationEngine.generate_response(
                user_message,
                article.content,
                mode,
                history
            )

            # 4. 保存对话历史
            await session.add_message(user_id, "user", user_message)
            await session.add_message(user_id, "assistant", response)

            # 5. 更新学习进度(如果在学习模式)
            if mode == "learning":
                await storage.connect()
                progress = await storage.get_or_create_progress(user_id, article.id)
                await storage.update_progress(
                    progress.id,
                    questions_asked=progress.questions_asked + 1
                )
                await storage.disconnect()

            await session.disconnect()

            # 6. 发送回复（优先使用 Markdown，失败则回退纯文本）
            try:
                await client.send_long_message(chat_id, response)
            except Exception as markdown_err:
                logger.warning(f"Markdown send failed, falling back to plain text: {markdown_err}")
                await client.send_long_message(chat_id, response, parse_mode=None)

            logger.info(f"Conversation handled for user {user_id} in {mode} mode")

        except Exception as e:
            logger.error(f"Failed to handle conversation: {e}")
            await client.send_message(
                chat_id,
                f"❌ 对话处理失败: {escape_markdown_v2(str(e))}"
            )
