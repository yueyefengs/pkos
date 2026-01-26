from lark_oapi.core.const import UTF_8
from lark_oapi.core.model import RawRequest, RawResponse


async def parse_req(request) -> RawRequest:
    """将 FastAPI Request 转换为 lark RawRequest"""
    req = RawRequest()
    req.uri = str(request.url.path)
    req.body = await request.body()
    req.headers = dict(request.headers)

    return req


def parse_resp(response: RawResponse):
    """将 lark RawResponse 转换为 FastAPI 响应"""
    from fastapi.responses import Response

    return Response(
        content=response.content,
        status_code=response.status_code,
        headers=dict(response.headers)
    )
