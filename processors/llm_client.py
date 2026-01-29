from typing import Optional
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
from config.settings import settings

class LLMClient:
    def __init__(self):
        self.config = settings.load_llm_config()
        self.default_model = self.config.get("default", "openai")
        self.clients = {}
        self._init_clients()

    def _init_clients(self):
        """初始化LLM客户端"""
        models = self.config.get("models", {})

        for name, model_config in models.items():
            model_type = model_config.get("type", "openai")

            if model_type == "openai":
                self.clients[name] = AsyncOpenAI(
                    api_key=model_config.get("api_key"),
                    base_url=model_config.get("base_url", "https://api.openai.com/v1")
                )
            elif model_type == "claude":
                self.clients[name] = AsyncAnthropic(
                    api_key=model_config.get("api_key")
                )

    async def optimize_content(self, content: str, prompt: str = "") -> str:
        """优化内容（修正错别字、智能分段）"""
        system_prompt = prompt or """你是一个专业的内容编辑。你的任务是优化转录文本：
1. 修正错别字和语音识别错误
2. 智能分段，按照语义和逻辑划分段落
3. 保持原意不变，不要添加或删减内容
4. 保持语言风格一致"""

        model_name = self.default_model
        model_config = self.config["models"].get(model_name, {})

        if model_config.get("type") == "claude":
            response = await self.clients[model_name].messages.create(
                model=model_config.get("model", "claude-3-5-sonnet-20241022"),
                max_tokens=8192,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": f"请优化以下内容：\n\n{content}"}
                ]
            )
            return response.content[0].text
        else:
            response = await self.clients[model_name].chat.completions.create(
                model=model_config.get("model", "gpt-4o"),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"请优化以下内容：\n\n{content}"}
                ],
                max_tokens=8192
            )
            return response.choices[0].message.content or content

    async def classify_content(self, content: str) -> str:
        """内容分类"""
        prompt = "请分析以下内容的主要类型：理论解释、技能教程、金融风险、人物传记、观点分析。只回答类型名称。"

        model_name = self.default_model
        model_config = self.config["models"].get(model_name, {})

        if model_config.get("type") == "claude":
            response = await self.clients[model_name].messages.create(
                model=model_config.get("model", "claude-3-5-sonnet-20241022"),
                max_tokens=100,
                messages=[
                    {"role": "user", "content": f"{prompt}\n\n内容：{content[:1000]}"}
                ]
            )
            return response.content[0].text.strip()
        else:
            response = await self.clients[model_name].chat.completions.create(
                model=model_config.get("model", "gpt-4o"),
                messages=[
                    {"role": "user", "content": f"{prompt}\n\n内容：{content[:1000]}"}
                ],
                max_tokens=100
            )
            return response.choices[0].message.content or "其他"

    async def generate_chat_response(self, prompt: str) -> str:
        """
        生成对话回复
        用于Telegram bot的对话功能

        Args:
            prompt: 完整的对话提示词(包含上下文和用户问题)

        Returns:
            str: AI生成的回复
        """
        model_name = self.default_model
        model_config = self.config["models"].get(model_name, {})

        if model_config.get("type") == "claude":
            response = await self.clients[model_name].messages.create(
                model=model_config.get("model", "claude-3-5-sonnet-20241022"),
                max_tokens=4096,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return response.content[0].text
        else:
            response = await self.clients[model_name].chat.completions.create(
                model=model_config.get("model", "gpt-4o"),
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=4096
            )
            return response.choices[0].message.content or "抱歉,我无法生成回复"

# 全局LLM客户端实例
llm_client = LLMClient()
