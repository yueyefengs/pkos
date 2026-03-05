from typing import Optional
import time
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
from config.settings import settings
from config.logger import logger

class LLMClient:
    def __init__(self):
        self.config = settings.load_llm_config()
        self.default_model = self.config.get("default", "openai")
        self.clients = {}
        # 根据模型类型设置max_tokens上限
        # Claude: 8192 tokens output
        # GPT-4o/GPT-4: 16384 tokens output (约48000汉字)
        self.max_tokens_limits = {
            "claude": 8192,
            "openai": 16384
        }
        # 输入内容长度阈值（字符数）
        # 超过此阈值会分块处理或警告
        self.content_length_threshold = 50000  # 约50k字符
        # LLM调用计数器（用于统计）
        self.call_count = 0
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

    def _log_llm_call(self, operation: str, model_name: str, model_type: str,
                      input_length: int, output_length: int,
                      duration: float, tokens_used: dict = None, error: str = None):
        """
        记录LLM调用详情

        Args:
            operation: 操作类型 (optimize_content/classify_content/generate_chat_response等)
            model_name: 模型名称 (openai/claude等)
            model_type: 模型类型 (gpt-4o/claude-3-5-sonnet等)
            input_length: 输入字符数
            output_length: 输出字符数
            duration: 耗时（秒）
            tokens_used: token使用情况 {"input": 100, "output": 200, "total": 300}
            error: 错误信息（如果有）
        """
        self.call_count += 1

        log_msg = (
            f"[LLM Call #{self.call_count}] "
            f"operation={operation} | "
            f"model={model_name}/{model_type} | "
            f"input={input_length} chars | "
            f"output={output_length} chars | "
            f"duration={duration:.2f}s"
        )

        if tokens_used:
            log_msg += f" | tokens(in={tokens_used.get('input', 0)}, out={tokens_used.get('output', 0)}, total={tokens_used.get('total', 0)})"

        if error:
            logger.error(f"{log_msg} | ERROR: {error}")
        else:
            logger.info(log_msg)

    async def optimize_content(self, content: str, prompt: str = "") -> str:
        """优化内容（修正错别字、智能分段）

        对于超长内容（>50k字符），会自动分块处理
        完整原文始终保存在 raw_transcript 字段，此方法返回的是优化后的版本
        """
        system_prompt = prompt or """你是一个专业的内容编辑。你的任务是优化转录文本：
1. 修正错别字和语音识别错误
2. 智能分段，按照语义和逻辑划分段落
3. 保持原意不变，不要添加或删减内容
4. 保持语言风格一致"""

        model_name = self.default_model
        model_config = self.config["models"].get(model_name, {})
        model_type = model_config.get("type", "openai")
        max_tokens = self.max_tokens_limits.get(model_type, 8192)

        content_length = len(content)
        logger.info(f"Optimizing content, length: {content_length} chars, max_tokens: {max_tokens}")

        # 如果内容超过阈值，分块处理
        if content_length > self.content_length_threshold:
            logger.warning(f"Content length ({content_length}) exceeds threshold ({self.content_length_threshold}), processing in chunks")
            return await self._optimize_content_chunked(content, system_prompt, model_name, model_config, max_tokens)

        # 正常处理
        start_time = time.time()
        try:
            actual_model = model_config.get("model", "gpt-4o" if model_type == "openai" else "claude-3-5-sonnet-20241022")

            if model_type == "claude":
                response = await self.clients[model_name].messages.create(
                    model=actual_model,
                    max_tokens=max_tokens,
                    system=system_prompt,
                    messages=[
                        {"role": "user", "content": f"请优化以下内容：\n\n{content}"}
                    ]
                )
                optimized = response.content[0].text

                # 记录token使用情况
                tokens_used = {
                    "input": response.usage.input_tokens,
                    "output": response.usage.output_tokens,
                    "total": response.usage.input_tokens + response.usage.output_tokens
                }
            else:
                response = await self.clients[model_name].chat.completions.create(
                    model=actual_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"请优化以下内容：\n\n{content}"}
                    ],
                    max_tokens=max_tokens
                )
                optimized = response.choices[0].message.content or content

                # 记录token使用情况
                tokens_used = {
                    "input": response.usage.prompt_tokens,
                    "output": response.usage.completion_tokens,
                    "total": response.usage.total_tokens
                }

            duration = time.time() - start_time

            # 记录日志
            self._log_llm_call(
                operation="optimize_content",
                model_name=model_name,
                model_type=actual_model,
                input_length=content_length,
                output_length=len(optimized),
                duration=duration,
                tokens_used=tokens_used
            )

            # 检查是否被截断
            if len(optimized) < content_length * 0.8:  # 如果优化后内容明显短于原文
                logger.warning(f"Optimized content ({len(optimized)} chars) is significantly shorter than original ({content_length} chars), possible truncation")

            return optimized
        except Exception as e:
            duration = time.time() - start_time
            self._log_llm_call(
                operation="optimize_content",
                model_name=model_name,
                model_type=model_config.get("model", "unknown"),
                input_length=content_length,
                output_length=0,
                duration=duration,
                error=str(e)
            )
            logger.error(f"Failed to optimize content: {e}")
            return content  # 失败时返回原文

    async def _optimize_content_chunked(self, content: str, system_prompt: str, model_name: str, model_config: dict, max_tokens: int) -> str:
        """分块优化长内容

        将长内容分成多个块，分别优化后合并
        每块大小约为阈值的一半，确保不会超出限制
        """
        chunk_size = self.content_length_threshold // 2  # 每块约25k字符
        chunks = []

        # 按段落分块（避免截断句子）
        paragraphs = content.split('\n\n')
        current_chunk = ""

        for para in paragraphs:
            if len(current_chunk) + len(para) + 2 <= chunk_size:
                current_chunk += para + "\n\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para + "\n\n"

        if current_chunk:
            chunks.append(current_chunk.strip())

        logger.info(f"Split content into {len(chunks)} chunks for processing")

        # 逐块优化
        optimized_chunks = []
        model_type = model_config.get("type", "openai")

        for i, chunk in enumerate(chunks):
            logger.info(f"Optimizing chunk {i+1}/{len(chunks)}, size: {len(chunk)} chars")

            start_time = time.time()
            try:
                actual_model = model_config.get("model", "gpt-4o" if model_type == "openai" else "claude-3-5-sonnet-20241022")

                if model_type == "claude":
                    response = await self.clients[model_name].messages.create(
                        model=actual_model,
                        max_tokens=max_tokens,
                        system=system_prompt,
                        messages=[
                            {"role": "user", "content": f"请优化以下内容片段（第{i+1}/{len(chunks)}部分）：\n\n{chunk}"}
                        ]
                    )
                    optimized_chunk = response.content[0].text
                    optimized_chunks.append(optimized_chunk)

                    # 记录token使用情况
                    tokens_used = {
                        "input": response.usage.input_tokens,
                        "output": response.usage.output_tokens,
                        "total": response.usage.input_tokens + response.usage.output_tokens
                    }
                else:
                    response = await self.clients[model_name].chat.completions.create(
                        model=actual_model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": f"请优化以下内容片段（第{i+1}/{len(chunks)}部分）：\n\n{chunk}"}
                        ],
                        max_tokens=max_tokens
                    )
                    optimized_chunk = response.choices[0].message.content or chunk
                    optimized_chunks.append(optimized_chunk)

                    # 记录token使用情况
                    tokens_used = {
                        "input": response.usage.prompt_tokens,
                        "output": response.usage.completion_tokens,
                        "total": response.usage.total_tokens
                    }

                duration = time.time() - start_time

                # 记录日志
                self._log_llm_call(
                    operation=f"optimize_content_chunk_{i+1}/{len(chunks)}",
                    model_name=model_name,
                    model_type=actual_model,
                    input_length=len(chunk),
                    output_length=len(optimized_chunk),
                    duration=duration,
                    tokens_used=tokens_used
                )
            except Exception as e:
                duration = time.time() - start_time
                self._log_llm_call(
                    operation=f"optimize_content_chunk_{i+1}/{len(chunks)}",
                    model_name=model_name,
                    model_type=model_config.get("model", "unknown"),
                    input_length=len(chunk),
                    output_length=0,
                    duration=duration,
                    error=str(e)
                )
                logger.error(f"Failed to optimize chunk {i+1}: {e}, using original chunk")
                optimized_chunks.append(chunk)

        # 合并所有优化后的块
        result = "\n\n".join(optimized_chunks)
        logger.info(f"Chunked optimization complete: {len(result)} chars output from {len(content)} chars input")
        return result

    async def classify_content(self, content: str) -> str:
        """内容分类"""
        prompt = "请分析以下内容的主要类型：理论解释、技能教程、金融风险、人物传记、观点分析。只回答类型名称。"
        content_sample = content[:1000]  # 只使用前1000字符进行分类

        model_name = self.default_model
        model_config = self.config["models"].get(model_name, {})
        model_type = model_config.get("type", "openai")
        actual_model = model_config.get("model", "gpt-4o" if model_type == "openai" else "claude-3-5-sonnet-20241022")

        start_time = time.time()
        try:
            if model_type == "claude":
                response = await self.clients[model_name].messages.create(
                    model=actual_model,
                    max_tokens=100,
                    messages=[
                        {"role": "user", "content": f"{prompt}\n\n内容：{content_sample}"}
                    ]
                )
                result = response.content[0].text.strip()

                # 记录token使用情况
                tokens_used = {
                    "input": response.usage.input_tokens,
                    "output": response.usage.output_tokens,
                    "total": response.usage.input_tokens + response.usage.output_tokens
                }
            else:
                response = await self.clients[model_name].chat.completions.create(
                    model=actual_model,
                    messages=[
                        {"role": "user", "content": f"{prompt}\n\n内容：{content_sample}"}
                    ],
                    max_tokens=100
                )
                result = response.choices[0].message.content or "其他"

                # 记录token使用情况
                tokens_used = {
                    "input": response.usage.prompt_tokens,
                    "output": response.usage.completion_tokens,
                    "total": response.usage.total_tokens
                }

            duration = time.time() - start_time

            # 记录日志
            self._log_llm_call(
                operation="classify_content",
                model_name=model_name,
                model_type=actual_model,
                input_length=len(content_sample),
                output_length=len(result),
                duration=duration,
                tokens_used=tokens_used
            )

            return result
        except Exception as e:
            duration = time.time() - start_time
            self._log_llm_call(
                operation="classify_content",
                model_name=model_name,
                model_type=actual_model,
                input_length=len(content_sample),
                output_length=0,
                duration=duration,
                error=str(e)
            )
            logger.error(f"Failed to classify content: {e}")
            return "其他"

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
        model_type = model_config.get("type", "openai")
        actual_model = model_config.get("model", "gpt-4o" if model_type == "openai" else "claude-3-5-sonnet-20241022")

        start_time = time.time()
        try:
            if model_type == "claude":
                response = await self.clients[model_name].messages.create(
                    model=actual_model,
                    max_tokens=4096,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                result = response.content[0].text

                # 记录token使用情况
                tokens_used = {
                    "input": response.usage.input_tokens,
                    "output": response.usage.output_tokens,
                    "total": response.usage.input_tokens + response.usage.output_tokens
                }
            else:
                response = await self.clients[model_name].chat.completions.create(
                    model=actual_model,
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=4096
                )
                result = response.choices[0].message.content or "抱歉,我无法生成回复"

                # 记录token使用情况
                tokens_used = {
                    "input": response.usage.prompt_tokens,
                    "output": response.usage.completion_tokens,
                    "total": response.usage.total_tokens
                }

            duration = time.time() - start_time

            # 记录日志
            self._log_llm_call(
                operation="generate_chat_response",
                model_name=model_name,
                model_type=actual_model,
                input_length=len(prompt),
                output_length=len(result),
                duration=duration,
                tokens_used=tokens_used
            )

            return result
        except Exception as e:
            duration = time.time() - start_time
            self._log_llm_call(
                operation="generate_chat_response",
                model_name=model_name,
                model_type=actual_model,
                input_length=len(prompt),
                output_length=0,
                duration=duration,
                error=str(e)
            )
            logger.error(f"Failed to generate chat response: {e}")
            return "抱歉,我无法生成回复"

# 全局LLM客户端实例
llm_client = LLMClient()
