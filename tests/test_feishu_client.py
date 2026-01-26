"""测试飞书客户端 - 单元测试"""
import pytest
import inspect


def test_feishu_client_exists():
    """FeishuClient 类应该存在并且有正确的方法"""
    from bot.feishu_client import FeishuClient

    # 验证类存在
    assert FeishuClient is not None

    # 验证方法存在
    client = FeishuClient()
    assert hasattr(client, 'send_message')
    assert hasattr(client, 'create_record')
    assert hasattr(client, 'client')

    # 验证 send_message 方法签名
    sig = inspect.signature(client.send_message)
    params = list(sig.parameters.keys())
    assert 'receive_id' in params
    assert 'content' in params
    assert 'msg_type' in params


def test_create_record_method_signature():
    """create_record 应该有正确的方法签名"""
    from bot.feishu_client import FeishuClient

    client = FeishuClient()
    sig = inspect.signature(client.create_record)
    params = list(sig.parameters.keys())

    assert 'title' in params
    assert 'video_url' in params
    assert 'content' in params
    assert sig.return_annotation == str
