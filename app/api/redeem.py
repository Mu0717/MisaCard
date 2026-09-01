"""已激活卡密的第三方删除接口代理。"""

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field


router = APIRouter(prefix="/redeem", tags=["redeem"])

THIRD_PARTY_DELETE_URL = "https://timoes.me/api/redeem/delete"
CARD_PROVIDER_SUFFIX = "-4513"


class RedeemDeleteRequest(BaseModel):
    code: str = Field(min_length=1)


def normalize_redeem_code(code: str) -> str:
    """仅移除卡密末尾用于识别供应商的 ``-4513`` 后缀。"""
    normalized = code.strip()
    if normalized.endswith(CARD_PROVIDER_SUFFIX):
        normalized = normalized.removesuffix(CARD_PROVIDER_SUFFIX)
    return normalized


@router.post("/delete")
async def delete_redeemed_card(request: RedeemDeleteRequest) -> Response:
    external_code = normalize_redeem_code(request.code)
    if not external_code:
        raise HTTPException(status_code=400, detail="卡密格式无效")

    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Content-Type": "application/json",
        "Referer": "https://timoes.me/",
        "User-Agent": "MisaCard/2.0",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            external_response = await client.post(
                THIRD_PARTY_DELETE_URL,
                headers=headers,
                json={"code": external_code},
            )
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="第三方删除接口请求超时") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"第三方删除接口请求失败: {exc}") from exc

    response_headers = {}
    content_type = external_response.headers.get("content-type")
    if content_type:
        response_headers["content-type"] = content_type

    return Response(
        content=external_response.content,
        status_code=external_response.status_code,
        headers=response_headers,
    )
