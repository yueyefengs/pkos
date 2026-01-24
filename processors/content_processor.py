from pathlib import Path
from processors.llm_client import llm_client

class ContentProcessor:
    def __init__(self):
        self.prompts_dir = Path("config/prompts")

    def load_prompt(self, prompt_name: str) -> str:
        """加载prompt模板"""
        prompt_file = self.prompts_dir / f"{prompt_name}.md"
        if prompt_file.exists():
            with open(prompt_file, 'r', encoding='utf-8') as f:
                return f.read()
        return ""

    async def process(self, content: str, title: str) -> str:
        """处理内容：优化、格式化

        Args:
            content: 原始转录内容
            title: 视频标题

        Returns:
            处理后的内容
        """
        # 首先分类内容
        content_type = await llm_client.classify_content(content)

        # 加载对应的prompt
        prompt = self.load_prompt(content_type)

        # 使用LLM优化内容
        optimized_content = await llm_client.optimize_content(content, prompt)

        # 格式化输出
        formatted_content = f"# {title}\n\n{optimized_content}"

        return formatted_content

# 全局内容处理器实例
content_processor = ContentProcessor()
