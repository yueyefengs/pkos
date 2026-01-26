import json
from config.settings import settings
from config.logger import setup_logger

logger = setup_logger("pkos.feishu_client")

class FeishuClient:
    """飞书官方SDK客户端 - 自动管理token和签名验证"""

    def __init__(self):
        import lark_oapi as lark
        self.client = lark.Client.builder() \
            .app_id(settings.feishu_app_id) \
            .app_secret(settings.feishu_app_secret) \
            .log_level(lark.LogLevel.INFO) \
            .build()

    def send_message(self, receive_id: str, msg_type: str = "text", content: str = ""):
        """发送消息 - SDK自动管理token"""
        from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody

        request = CreateMessageRequest.builder() \
            .receive_id_type("open_id") \
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(receive_id)
                .msg_type(msg_type)
                .content(json.dumps({"text": content}))
                .build()
            ).build()

        response = self.client.im.v1.message.create(request)

        if not response.success():
            logger.error(f"发送消息失败: {response.code} - {response.msg}")
            raise Exception(f"发送消息失败: {response.msg}")

        logger.debug("Message sent successfully to %s", receive_id)
        return response.data

    def create_record(self, title: str, video_url: str, content: str) -> str:
        """在多维表格中创建记录

        Returns:
            记录ID
        """
        from lark_oapi.api.bitable.v1 import (
            CreateAppTableRecordRequest,
            CreateAppTableRecordRequestBody
        )

        logger.debug("Creating record in bitable: %s", title[:50])

        request = CreateAppTableRecordRequest.builder() \
            .app_token(settings.feishu_bitable_token) \
            .table_id(settings.feishu_bitable_table_id) \
            .request_body(
                CreateAppTableRecordRequestBody.builder()
                .fields({
                    "标题": title,
                    "来源URL": video_url,
                    "处理状态": "已完成",
                    "文稿内容": content
                })
                .build()
            ).build()

        response = self.client.bitable.v1.app_table_record.create(request)

        if not response.success():
            logger.error(f"创建记录失败: {response.code} - {response.msg}")
            raise Exception(f"创建记录失败: {response.msg}")

        record_id = response.data.record.record_id
        logger.info("Record created successfully: %s", record_id)
        return record_id

# 全局飞书客户端实例
feishu_client = FeishuClient()
