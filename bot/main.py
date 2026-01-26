from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
import uvicorn
from config.settings import settings
from config.logger import logger
from bot.feishu_client import feishu_client
from bot.webhook import webhook_handler

app = FastAPI(title="Feishu Knowledge Bot", version="1.0.0")

@app.on_event("startup")
async def startup():
    """服务启动时的初始化"""
    try:
        token = await feishu_client.get_tenant_access_token()
        logger.info("Successfully connected to Feishu API")
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
    """处理飞书事件"""
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="Empty request body")
    data = await request.json()

    # 验证URL签名
    if "url_verify" in data:
        challenge = data.get("challenge", "")
        # 飞书 URL 验证需要直接返回 challenge 字符串
        return PlainTextResponse(content=challenge)

    # 验证事件签名
    headers = request.headers
    timestamp = headers.get("X-Lark-Request-Timestamp", "")
    nonce = headers.get("X-Lark-Request-Nonce", "")
    signature = headers.get("X-Lark-Signature", "")

    if not feishu_client.verify_event(timestamp, nonce, body.decode(), signature):
        logger.warning("Invalid signature for request from %s", request.client)
        raise HTTPException(status_code=403, detail="Invalid signature")

    # 处理事件
    event = data.get("event", {})
    event_type = event.get("type", "")

    logger.debug("Received event type: %s", event_type)

    if event_type == "message.receive_v1":
        result = await webhook_handler.handle_message(event)
        logger.info("Message handled successfully")

    return JSONResponse(content={"code": 0, "msg": "success"})

if __name__ == "__main__":
    uvicorn.run(
        "bot.main:app",
        host=settings.host,
        port=settings.port,
        reload=True
    )
