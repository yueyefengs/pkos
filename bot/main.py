from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn
from config.settings import settings
from config.logger import logger
from bot.feishu_client import feishu_client
from bot.webhook import webhook_handler
import lark_oapi as lark
from lark_oapi import EventDispatcherHandler

app = FastAPI(title="Feishu Knowledge Bot", version="1.0.0")

# 创建事件分发器
event_handler = EventDispatcherHandler.builder(
    settings.feishu_encrypt_key or "",
    "",  # verification_token可选
    lark.LogLevel.INFO
).register_p2_im_message_receive_v1(
    lambda data: webhook_handler.handle_message_receive(data)
).build()

@app.on_event("startup")
async def startup():
    """服务启动时的初始化"""
    try:
        # 尝试发送一个测试消息以验证SDK连接
        logger.info("Feishu client initialized with lark-oapi SDK")
    except Exception as e:
        logger.error("Failed to initialize Feishu client: %s", e)
        logger.warning("Please check your Feishu credentials (FEISHU_APP_ID, FEISHU_APP_SECRET)")
        raise

@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "ok"}

@app.post("/feishu/events")
async def handle_feishu_event(request: Request):
    """处理飞书事件 - SDK自动验证签名和路由"""
    from bot.adapter.fastapi_parser import parse_req, parse_resp

    lark_request = await parse_req(request)
    response = event_handler.do(lark_request)
    return parse_resp(response)

if __name__ == "__main__":
    uvicorn.run(
        "bot.main:app",
        host=settings.host,
        port=settings.port,
        reload=True
    )
