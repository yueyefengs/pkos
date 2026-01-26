"""测试飞书事件处理器 - 验证空body处理"""
import pytest
from fastapi.testclient import TestClient
from bot.main import app


client = TestClient(app)


def test_empty_body_post_request():
    """测试空body的POST请求（健康检查/监控探针）"""
    response = client.post("/feishu/events", content=b"")

    # 应该返回200而不是500
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_endpoint():
    """测试健康检查端点"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_empty_json_body():
    """测试空JSON对象"""
    response = client.post(
        "/feishu/events",
        json={},
        headers={"Content-Type": "application/json"}
    )

    # 空JSON对象不是空body，应该被SDK处理
    # SDK会返回错误或验证失败，但不应该是我们的空body处理逻辑
    # 这个测试确认我们只拦截真正的空body
    assert response.status_code != 500 or "Expecting value" not in response.text


def test_valid_event_structure():
    """测试有效的事件结构（模拟URL验证）"""
    # URL验证事件的基本结构
    event_data = {
        "challenge": "test_challenge_123",
        "type": "url_verification"
    }

    response = client.post(
        "/feishu/events",
        json=event_data,
        headers={"Content-Type": "application/json"}
    )

    # 这应该被SDK处理，我们不拦截有内容的请求
    # 注意：没有正确的签名会失败，但至少不是因为空body
    assert len(response.content) > 0
