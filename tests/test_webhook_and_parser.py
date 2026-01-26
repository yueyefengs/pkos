"""测试 WebhookHandler"""
import pytest
from unittest.mock import Mock, patch


class TestWebhookHandler:
    """测试 WebhookHandler"""

    def test_extract_video_url(self):
        """_extract_video_url 应该正确提取URL"""
        from bot.webhook import WebhookHandler

        handler = WebhookHandler()

        # 测试有效URL
        url = handler._extract_video_url("请帮忙处理这个视频 https://www.bilibili.com/video/BV123456")
        assert url == "https://www.bilibili.com/video/BV123456"

        # 测试无URL
        url = handler._extract_video_url("这是普通消息没有链接")
        assert url == ""

    def test_extract_video_url_multiple_urls(self):
        """_extract_video_url 应该返回第一个URL"""
        from bot.webhook import WebhookHandler

        handler = WebhookHandler()

        url = handler._extract_video_url("链接1: https://bilibili.com/1 和链接2: https://douyin.com/2")
        assert url == "https://bilibili.com/1"


class TestFastAPIParser:
    """测试 FastAPI 解析器"""

    @pytest.mark.asyncio
    async def test_parse_req_creates_raw_request(self):
        """parse_req 应该创建正确的 RawRequest"""
        from bot.adapter.fastapi_parser import parse_req
        from fastapi import Request

        # 创建 mock request
        mock_request = Mock(spec=Request)
        mock_request.url.path = "/feishu/events"
        mock_request.headers = {"Content-Type": "application/json"}
        mock_request.body.return_value = b'{"type":"test"}'

        # 执行
        from lark_oapi.core.model import RawRequest
        result = await parse_req(mock_request)

        # 验证
        assert isinstance(result, RawRequest)
        assert result.uri == "/feishu/events"

    def test_parse_resp_creates_fastapi_response(self):
        """parse_resp 应该创建 FastAPI Response"""
        from bot.adapter.fastapi_parser import parse_resp
        from lark_oapi.core.model import RawResponse

        # 创建 mock response
        mock_response = RawResponse()
        mock_response.content = "challenge_string"
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "text/plain"}

        # 执行
        result = parse_resp(mock_response)

        # 验证
        assert result.status_code == 200
        assert result.body == b"challenge_string"
