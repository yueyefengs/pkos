from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn
import threading
from config.settings import settings
from config.logger import logger
from bot.feishu_client import feishu_client
from bot.webhook import webhook_handler
import lark_oapi as lark
from lark_oapi import EventDispatcherHandler

app = FastAPI(title="Feishu Knowledge Bot", version="1.0.0")

# 创建事件分发器
# 注意：长链接模式不需要 encrypt_key 和 verification_token
event_handler = EventDispatcherHandler.builder(
    settings.feishu_encrypt_key or "" if settings.feishu_event_mode == "webhook" else "",
    "",  # verification_token可选
    lark.LogLevel.INFO
).register_p2_im_message_receive_v1(
    lambda data: webhook_handler.handle_message_receive(data)
).build()

# WebSocket 客户端（仅在长链接模式下使用）
ws_client = None

def start_websocket_client():
    """启动 WebSocket 长链接客户端（在独立事件循环中运行）"""
    import asyncio
    global ws_client

    try:
        # 为新线程创建独立的事件循环
        # 这样可以避免与 FastAPI 的 uvloop 冲突
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)

        logger.info("Starting Feishu WebSocket long connection client...")
        logger.info("Creating new event loop for WebSocket thread...")

        # 修补 SDK 模块的事件循环引用
        # SDK 在模块级别缓存了事件循环，需要更新为新循环
        import lark_oapi.ws.client as ws_client_module
        ws_client_module.loop = new_loop

        ws_client = lark.ws.Client(
            settings.feishu_app_id,
            settings.feishu_app_secret,
            event_handler=event_handler,
            log_level=lark.LogLevel.INFO
        )

        logger.info("WebSocket client initialized, connecting...")
        ws_client.start()  # 这会阻塞，但在独立线程中运行没问题
        logger.info("✅ WebSocket client connected successfully")
    except Exception as e:
        logger.error("Failed to start WebSocket client: %s", e)
        import traceback
        logger.error("Traceback: %s", traceback.format_exc())
        raise

def start_websocket_thread():
    """在独立线程中启动 WebSocket 客户端"""
    thread = threading.Thread(target=start_websocket_client, daemon=True, name="FeishuWebSocketClient")
    thread.start()
    logger.info("WebSocket client thread started")

@app.on_event("startup")
async def startup():
    """服务启动时的初始化"""
    try:
        # 根据配置选择事件接收模式
        if settings.feishu_event_mode == "websocket":
            logger.info("📡 Using WebSocket long connection mode for event reception")
            start_websocket_thread()
        else:
            logger.info("🔗 Using Webhook mode for event reception")

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
    """
    处理飞书事件 (Webhook 模式) - SDK自动验证签名和路由

    注意：如果使用 WebSocket 长链接模式 (FEISHU_EVENT_MODE=websocket)，
    此端点将不会被飞书调用。建议切换到长链接模式以简化部署。
    """
    # 如果配置为长链接模式，记录警告
    if settings.feishu_event_mode == "websocket":
        logger.warning("⚠️ Webhook endpoint called but system is configured for WebSocket mode")
        return JSONResponse(
            content={"error": "System configured for WebSocket mode, webhook not available"},
            status_code=503
        )

    from bot.adapter.fastapi_parser import parse_req, parse_resp

    lark_request = await parse_req(request)

    # Debug logging
    logger.info("=== Feishu Event Received (Webhook) ===")
    logger.info("URI: %s", lark_request.uri)
    logger.info("Headers: %s", lark_request.headers)
    logger.info("Body length: %d bytes", len(lark_request.body))
    logger.info("Body preview: %s", lark_request.body[:200] if lark_request.body else b"<empty>")
    logger.info("Content-Type: %s", lark_request.headers.get("Content-Type", "<not set>"))

    # Handle empty body (health checks, monitoring probes)
    if not lark_request.body or len(lark_request.body) == 0:
        logger.warning("Received request with empty body - likely health check or monitoring probe")
        logger.info("Response status: 200")
        logger.info("=== End Feishu Event ===")
        return JSONResponse(content={"status": "ok"}, status_code=200)

    response = event_handler.do(lark_request)

    logger.info("Response status: %d", response.status_code)
    logger.info("=== End Feishu Event ===")

    return parse_resp(response)

if __name__ == "__main__":
    uvicorn.run(
        "bot.main:app",
        host=settings.host,
        port=settings.port,
        reload=True
    )
