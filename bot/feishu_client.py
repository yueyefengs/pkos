import hashlib
import hmac
import base64
import json
import httpx
from typing import Optional
from config.settings import settings

class FeishuClient:
    def __init__(self):
        self.app_id = settings.feishu_app_id
        self.app_secret = settings.feishu_app_secret
        self.encrypt_key = settings.feishu_encrypt_key
        self.bitable_token = settings.feishu_bitable_token
        self.bitable_table_id = settings.feishu_bitable_table_id
        self.tenant_access_token: Optional[str] = None
        self.base_url = "https://open.feishu.cn/open-apis"

    async def get_tenant_access_token(self) -> str:
        """获取tenant_access_token"""
        if self.tenant_access_token:
            return self.tenant_access_token

        # 打印调试信息（注意：生产环境应移除敏感信息）
        print(f"Getting tenant access token with App ID: {self.app_id}")
        print(f"App Secret length: {len(self.app_secret) if self.app_secret else 0}")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/auth/v3/tenant_access_token/internal",
                json={
                    "app_id": self.app_id,
                    "app_secret": self.app_secret
                }
            )
            response.raise_for_status()
            data = response.json()

            print(f"Feishu API response: {data}")

            # 检查API返回的错误码
            if "code" in data and data["code"] != 0:
                raise ValueError(
                    f"Feishu API error: {data.get('msg', 'Unknown error')} "
                    f"(code: {data['code']})"
                )

            # 检查token是否存在
            if "tenant_access_token" not in data:
                raise ValueError(
                    f"Feishu API response missing tenant_access_token. "
                    f"Response: {data}"
                )

            self.tenant_access_token = data["tenant_access_token"]
            print(f"Successfully got tenant access token")
            return self.tenant_access_token

    def verify_event(self, timestamp: str, nonce: str, body: str, signature: str) -> bool:
        """验证飞书事件签名"""
        if not self.encrypt_key:
            return True  # 如果没有配置加密密钥，跳过验证

        key = base64.b64decode(self.encrypt_key)
        message = f"{timestamp}{nonce}{body}".encode()
        expected_signature = hmac.new(key, message, hashlib.sha256).hexdigest()
        return expected_signature == signature

    async def send_message(self, receive_id: str, msg_type: str = "text", content: str = ""):
        """发送消息"""
        token = await self.get_tenant_access_token()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/im/v1/messages?receive_id_type=open_id",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                json={
                    "receive_id": receive_id,
                    "msg_type": msg_type,
                    "content": json.dumps({"text": content})
                }
            )
            response.raise_for_status()
            return response.json()

    async def create_record(self, title: str, video_url: str, content: str) -> str:
        """在多维表格中创建记录

        Returns:
            记录ID
        """
        token = await self.get_tenant_access_token()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/bitable/v1/apps/{self.bitable_token}/tables/{self.bitable_table_id}/records",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                json={
                    "fields": {
                        "标题": title,
                        "来源URL": video_url,
                        "处理状态": "已完成",
                        "文稿内容": content
                    }
                }
            )
            response.raise_for_status()
            data = response.json()
            return data["data"]["record"]["record_id"]

# 全局飞书客户端实例
feishu_client = FeishuClient()
