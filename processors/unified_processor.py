"""
统一内容处理器 - 融合卡帕西工作流
支持视频、文章、音频、文本的统一摄入和消化
"""
import re
from html import unescape
from html.parser import HTMLParser
from typing import Optional, Tuple
from pathlib import Path
from datetime import datetime
import uuid

from config.settings import settings
from config.logger import logger
from processors.llm_client import llm_client


class UnifiedProcessor:
    """统一内容处理器"""
    
    def __init__(self):
        self.temp_dir = Path("temp")
        self.temp_dir.mkdir(exist_ok=True)
        
        # Obsidian 知识库路径
        vault = getattr(settings, "obsidian_vault_path", None)
        self.vault_path = Path(vault) if vault else None
        
        # 目录结构
        if self.vault_path:
            self.raw_dir = self.vault_path / "raw"
            self.wiki_dir = self.vault_path / "wiki"
            self.index_file = self.vault_path / "index.md"
            self.log_file = self.vault_path / "log.md"
    
    # ========================================================================
    # 内容类型检测
    # ========================================================================
    
    def detect_content_type(self, content: str) -> str:
        """
        自动检测内容类型
        
        Returns:
            'video' | 'article' | 'audio' | 'text'
        """
        content = content.strip()
        
        # 视频链接
        if any(x in content for x in ['douyin.com', 'iesdouyin.com', 'bilibili.com', 'b23.tv', 'youtube.com', 'youtu.be']):
            return 'video'
        
        # 音频链接
        if any(content.lower().endswith(ext) for ext in ['.mp3', '.m4a', '.wav', '.ogg', '.flac']):
            return 'audio'
        
        # 文章链接（网页）
        if content.startswith('http://') or content.startswith('https://'):
            return 'article'
        
        # 默认为文本
        return 'text'
    
    # ========================================================================
    # 内容获取
    # ========================================================================
    
    async def fetch_video(self, url: str) -> Tuple[str, str, str]:
        """
        下载视频并转录
        
        Returns:
            (title, transcript, processed_content)
        """
        from processors.video_downloader import video_downloader
        from processors.transcriber import transcriber
        from processors.content_processor import content_processor
        
        # 下载
        audio_path, title = await video_downloader.download(url)
        logger.info(f"[Unified] Downloaded: {title}")
        
        # 转录
        transcript = transcriber.transcribe(audio_path)
        logger.info(f"[Unified] Transcribed: {len(transcript)} chars")
        
        # 优化
        processed = await content_processor.process(transcript, title)
        logger.info(f"[Unified] Processed: {len(processed)} chars")
        
        return title, transcript, processed
    
    async def fetch_article(self, url: str) -> Tuple[str, str]:
        """
        提取文章内容
        
        Returns:
            (title, content)
        """
        import httpx
        
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            response = await client.get(url, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            })
            html = response.text
        
        title = self._extract_html_title(html)

        # 优先使用 readability，缺失时回退到内置提取逻辑
        try:
            from readability.readability import Document
            doc = Document(html)
            title = doc.title() or title
            content = doc.summary()
        except ImportError:
            logger.warning("[Unified] readability not installed, using fallback article extraction")
            content = self._extract_article_fallback(html)
        
        # HTML 转 Markdown（简化版）
        content = self._html_to_markdown(content)
        if not content.strip():
            raise ValueError("文章正文提取失败")
        
        logger.info(f"[Unified] Fetched article: {title}, {len(content)} chars")
        return title, content
    
    async def fetch_audio(self, url: str) -> Tuple[str, str, str]:
        """
        下载音频并转录
        
        Returns:
            (title, transcript, processed_content)
        """
        import httpx
        from processors.transcriber import transcriber
        from processors.content_processor import content_processor
        
        # 下载音频
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.get(url)
            audio_data = response.content
        
        # 保存临时文件
        ext = url.split('.')[-1].split('?')[0] or 'm4a'
        audio_path = self.temp_dir / f"audio_{uuid.uuid4().hex[:8]}.{ext}"
        audio_path.write_bytes(audio_data)
        
        title = audio_path.stem
        
        # 转录
        transcript = transcriber.transcribe(str(audio_path))
        
        # 优化
        processed = await content_processor.process(transcript, title)
        
        return title, transcript, processed
    
    def _html_to_markdown(self, html: str) -> str:
        """简化的 HTML 转 Markdown"""
        import re
        
        # 移除 script 和 style
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL|re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL|re.IGNORECASE)
        
        # 转换常见标签
        html = re.sub(r'<h1[^>]*>(.*?)</h1>', r'# \1\n', html, flags=re.DOTALL)
        html = re.sub(r'<h2[^>]*>(.*?)</h2>', r'## \1\n', html, flags=re.DOTALL)
        html = re.sub(r'<h3[^>]*>(.*?)</h3>', r'### \1\n', html, flags=re.DOTALL)
        html = re.sub(r'<p[^>]*>(.*?)</p>', r'\1\n\n', html, flags=re.DOTALL)
        html = re.sub(r'<br\s*/?>', '\n', html)
        html = re.sub(r'<strong[^>]*>(.*?)</strong>', r'**\1**', html, flags=re.DOTALL)
        html = re.sub(r'<b[^>]*>(.*?)</b>', r'**\1**', html, flags=re.DOTALL)
        html = re.sub(r'<em[^>]*>(.*?)</em>', r'*\1*', html, flags=re.DOTALL)
        html = re.sub(r'<i[^>]*>(.*?)</i>', r'*\1*', html, flags=re.DOTALL)
        html = re.sub(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', r'[\2](\1)', html, flags=re.DOTALL)
        html = re.sub(r'<li[^>]*>(.*?)</li>', r'- \1\n', html, flags=re.DOTALL)
        
        # 移除剩余标签
        html = re.sub(r'<[^>]+>', '', html)
        
        # 清理
        html = re.sub(r'\n{3,}', '\n\n', html)
        html = unescape(html)
        
        return html.strip()

    def _extract_html_title(self, html: str) -> str:
        """从 HTML 中提取标题"""
        match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.DOTALL | re.IGNORECASE)
        if not match:
            return f"文章-{datetime.now().strftime('%H%M%S')}"
        title = re.sub(r"\s+", " ", unescape(match.group(1))).strip()
        return title or f"文章-{datetime.now().strftime('%H%M%S')}"

    def _extract_article_fallback(self, html: str) -> str:
        """readability 不可用时的轻量正文提取"""
        class ArticleTextExtractor(HTMLParser):
            def __init__(self):
                super().__init__()
                self.parts = []
                self.skip_depth = 0
                self.block_tags = {"p", "div", "section", "article", "li", "h1", "h2", "h3", "h4", "blockquote", "br"}

            def handle_starttag(self, tag, attrs):
                if tag in {"script", "style", "noscript"}:
                    self.skip_depth += 1
                    return
                if self.skip_depth == 0 and tag in self.block_tags:
                    self.parts.append("\n")

            def handle_endtag(self, tag):
                if tag in {"script", "style", "noscript"} and self.skip_depth > 0:
                    self.skip_depth -= 1
                    return
                if self.skip_depth == 0 and tag in self.block_tags:
                    self.parts.append("\n")

            def handle_data(self, data):
                if self.skip_depth == 0:
                    text = data.strip()
                    if text:
                        self.parts.append(text)

        extractor = ArticleTextExtractor()
        extractor.feed(html)
        text = "\n".join(extractor.parts)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()
    
    # ========================================================================
    # 摄取到 Raw
    # ========================================================================
    
    def ingest_to_raw(
        self,
        content: str,
        source_type: str,
        title: str = "",
        source_url: str = ""
    ) -> str:
        """
        摄取内容到 /raw 目录
        
        Returns:
            raw 文件路径
        """
        if not self.vault_path:
            raise ValueError("OBSIDIAN_VAULT_PATH 未配置")
        
        # 确保目录存在
        raw_subdir = self.raw_dir / source_type
        raw_subdir.mkdir(parents=True, exist_ok=True)
        
        # 生成文件名
        date_str = datetime.now().strftime("%Y-%m-%d")
        safe_title = self._sanitize_filename(title or f"{source_type}-{date_str}")
        filepath = raw_subdir / f"{date_str}-{safe_title}.md"
        
        # 文件名冲突处理
        if filepath.exists():
            filepath = raw_subdir / f"{date_str}-{safe_title}-{datetime.now().strftime('%H%M%S')}.md"
        
        # 写入文件
        note_content = f"""---
title: {title}
source: {source_url}
type: {source_type}
created: {datetime.now().isoformat()}
---

{content}
"""
        filepath.write_text(note_content, encoding="utf-8")
        
        logger.info(f"[Unified] Ingested to raw: {filepath}")
        return str(filepath)
    
    # ========================================================================
    # 消化到 Wiki（异步）
    # ========================================================================
    
    async def digest_to_wiki(self, raw_file: str) -> list:
        """
        将 raw 文件消化为 wiki 笔记（异步）
        
        Returns:
            创建的 wiki 文件路径列表
        """
        if not self.vault_path:
            raise ValueError("OBSIDIAN_VAULT_PATH 未配置")
        
        raw_path = Path(raw_file)
        if not raw_path.exists():
            logger.error(f"[Unified] Raw file not found: {raw_file}")
            raise FileNotFoundError(f"Raw file not found: {raw_file}")
        
        # 读取 raw 内容
        raw_content = raw_path.read_text(encoding="utf-8")
        
        # 提取 frontmatter
        title = raw_path.stem
        fm_match = re.search(r"^---\n(.*?)\n---", raw_content, re.DOTALL)
        if fm_match:
            for line in fm_match.group(1).splitlines():
                if line.startswith("title:"):
                    title = line[6:].strip()
        
        # 提取正文
        body = re.sub(r"^---\n.*?\n---\n", "", raw_content, flags=re.DOTALL)
        
        # 调用 LLM 消化
        prompt = self._build_digest_prompt(str(raw_path.relative_to(self.vault_path)), title, body[:10000])
        
        try:
            result = await llm_client.generate_chat_response(prompt)
        except Exception as e:
            logger.error(f"[Unified] Digest failed: {e}")
            raise RuntimeError(f"知识消化失败: {e}") from e
        
        # 解析并创建 wiki 笔记
        notes = self._parse_digest_result(result)
        if not notes:
            raise ValueError("知识消化失败: 未生成有效 wiki 笔记")
        created_paths = []
        
        for note in notes:
            note_type = self._classify_note_type(note["title"], note["content"])
            wiki_subdir = self.wiki_dir / note_type
            wiki_subdir.mkdir(parents=True, exist_ok=True)
            
            safe_title = self._sanitize_filename(note["title"])
            filepath = wiki_subdir / f"{safe_title}.md"
            
            # 写入笔记
            note_content = f"""---
title: {note['title']}
created: {datetime.now().isoformat()}
source: {raw_path.name}
tags: {note.get('tags', '')}
---

{note['content']}

---
**来源**：[[{raw_path.stem}]]
**相关条目**：{note.get('related', '无')}
"""
            filepath.write_text(note_content, encoding="utf-8")
            created_paths.append(str(filepath))
        
        if not created_paths:
            raise ValueError("知识消化失败: wiki 笔记写入为空")

        logger.info(f"[Unified] Digested to {len(created_paths)} wiki notes")
        return created_paths
    
    def _build_digest_prompt(self, raw_path: str, title: str, content: str) -> str:
        """构建消化提示词"""
        return f"""# 角色：原子化知识消化专家

你是专业的知识拆解工具，核心目标是将原始资料转化为**可复用、可链接、原子化**的知识库条目。

## 当前任务
将以下原始资料消化为原子化知识笔记。

## 原始资料
文件路径：{raw_path}
标题：{title}

内容：
{content}

## 执行规则
1. **原子化原则**：每条笔记只表达一个明确主题/独立知识单元，严禁将多个概念、论点、案例混写在同一条笔记中。
2. **可独立理解**：每条笔记必须脱离原始上下文也能被读懂，标题需清晰、具体、可检索。
3. **提炼而非照搬**：不直接复制 raw 内容，不做简单摘要，而是将内容拆解、改写、提炼为可长期复用的知识单元。
4. **优先拆解维度**：优先提取「概念、事实、方法、证据、观点」5类核心内容；若一段内容包含多个意思，必须拆分为多条笔记。
5. **知识关联**：笔记之间尽量建立关联，补充相关条目、回链建议和标签，避免形成知识孤岛。
6. **价值筛选**：舍弃不值得沉淀为独立条目的信息，不制造低价值笔记。

## 输出格式
每条笔记格式如下：

---
# [笔记标题]

[笔记正文内容]

**来源**：{raw_path}
**相关条目**：[[相关笔记1]], [[相关笔记2]]
**标签**：#标签1 #标签2
---

请输出所有拆解后的笔记，每条笔记用 `---` 分隔。"""
    
    def _parse_digest_result(self, result: str) -> list:
        """解析 LLM 消化结果"""
        notes = []
        blocks = re.split(r"\n---\n", result)
        
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            
            # 提取标题
            title_match = re.search(r"^#\s+(.+)$", block, re.MULTILINE)
            if not title_match:
                continue
            
            title = title_match.group(1).strip()
            
            # 提取标签
            tags_match = re.search(r"\*\*标签\*\*[：:]\s*(.+)$", block, re.MULTILINE)
            tags = tags_match.group(1).strip() if tags_match else ""
            
            # 提取相关条目
            related_match = re.search(r"\*\*相关条目\*\*[：:]\s*(.+)$", block, re.MULTILINE)
            related = related_match.group(1).strip() if related_match else ""
            
            # 提取正文
            content = re.sub(r"^#\s+.+$", "", block, count=1, flags=re.MULTILINE)
            content = re.sub(r"\n---\n.*$", "", content, flags=re.DOTALL)
            content = content.strip()
            
            notes.append({
                "title": title,
                "content": content,
                "tags": tags,
                "related": related
            })
        
        return notes
    
    def _classify_note_type(self, title: str, content: str) -> str:
        """判断笔记类型"""
        title_lower = title.lower()
        
        # 人物
        person_keywords = ["访谈", "人物", "简介", "是谁", "生平"]
        if any(kw in title for kw in person_keywords):
            return "人物"
        
        # 方法
        method_keywords = ["方法", "如何", "怎样", "步骤", "流程", "技巧", "指南", "法则"]
        if any(kw in title for kw in method_keywords):
            return "方法"
        
        # 案例
        case_keywords = ["案例", "实例", "例子", "经历", "故事"]
        if any(kw in title for kw in case_keywords):
            return "案例"
        
        # 观点
        opinion_keywords = ["观点", "看法", "认为", "应该", "思考", "启示"]
        if any(kw in title for kw in opinion_keywords):
            return "观点"
        
        # 公司
        company_keywords = ["公司", "企业", "创业", "组织", "品牌"]
        if any(kw in title for kw in company_keywords):
            return "公司"
        
        # 默认：概念
        return "概念"
    
    # ========================================================================
    # 健康检查
    # ========================================================================
    
    async def lint_wiki(self) -> dict:
        """
        知识库健康检查（轻量版）
        
        Returns:
            检查结果摘要
        """
        if not self.vault_path:
            return {"status": "disabled"}
        
        wiki_files = list(self.wiki_dir.rglob("*.md")) if self.wiki_dir.exists() else []
        
        # 简单统计
        by_type = {}
        for f in wiki_files:
            note_type = f.parent.name
            by_type[note_type] = by_type.get(note_type, 0) + 1
        
        return {
            "status": "ok",
            "total_notes": len(wiki_files),
            "by_type": by_type
        }
    
    # ========================================================================
    # 索引更新
    # ========================================================================
    
    def update_index(self) -> int:
        """更新知识库索引"""
        if not self.vault_path:
            return 0
        
        wiki_files = list(self.wiki_dir.rglob("*.md")) if self.wiki_dir.exists() else []
        
        # 按类型分组
        by_type = {}
        for f in wiki_files:
            note_type = f.parent.name
            if note_type not in by_type:
                by_type[note_type] = []
            title = f.stem
            by_type[note_type].append(title)
        
        # 生成索引
        index_content = f"""# 知识库索引

> 更新时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
> 笔记总数：{len(wiki_files)}

## 按类型浏览

"""
        
        for note_type, titles in sorted(by_type.items()):
            index_content += f"### {note_type} ({len(titles)})\n\n"
            for title in titles[:30]:
                index_content += f"- [[{title}]]\n"
            if len(titles) > 30:
                index_content += f"  - ... 还有 {len(titles) - 30} 条\n"
            index_content += "\n"
        
        self.index_file.write_text(index_content, encoding="utf-8")
        return len(wiki_files)
    
    # ========================================================================
    # 工具方法
    # ========================================================================
    
    def _sanitize_filename(self, title: str) -> str:
        """去除文件名非法字符"""
        safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", title)
        safe = safe.strip(". ")
        return safe[:50] or "untitled"


# 单例
unified_processor = UnifiedProcessor()
