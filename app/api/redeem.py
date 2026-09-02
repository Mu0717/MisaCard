"""已激活卡密的第三方删除接口代理。"""

import asyncio

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator


router = APIRouter(prefix="/redeem", tags=["redeem"])

THIRD_PARTY_DELETE_URL = "https://timoes.me/api/redeem/delete"
CARD_PROVIDER_SUFFIX = "-4513"


class RedeemDeleteRequest(BaseModel):
    code: str = Field(min_length=1)


class RedeemBatchDeleteRequest(BaseModel):
    codes: list[str] = Field(min_length=1, max_length=100)
    concurrency: int = Field(default=5, ge=1, le=10)

    @field_validator("codes")
    @classmethod
    def normalize_codes(cls, values: list[str]) -> list[str]:
        normalized = []
        seen = set()
        for value in values:
            if not isinstance(value, str):
                raise ValueError("卡密必须是字符串")
            code = value.strip()
            if code and code not in seen:
                normalized.append(code)
                seen.add(code)
        if not normalized:
            raise ValueError("卡密列表不能为空")
        return normalized


def normalize_redeem_code(code: str) -> str:
    """仅移除卡密末尾用于识别供应商的 ``-4513`` 后缀。"""
    normalized = code.strip()
    if normalized.endswith(CARD_PROVIDER_SUFFIX):
        normalized = normalized.removesuffix(CARD_PROVIDER_SUFFIX)
    return normalized


def third_party_headers() -> dict[str, str]:
    return {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Content-Type": "application/json",
        "Referer": "https://timoes.me/",
        "User-Agent": "MisaCard/2.0",
    }


def third_party_result(response: httpx.Response) -> tuple[bool, str]:
    try:
        payload = response.json()
    except ValueError:
        payload = response.text.strip()

    if isinstance(payload, dict):
        message = payload.get("message") or payload.get("detail") or payload.get("msg")
        explicitly_failed = payload.get("success") is False
    else:
        message = payload if isinstance(payload, str) else None
        explicitly_failed = False

    success = response.is_success and not explicitly_failed
    if not message:
        message = "删除成功" if success else f"删除失败（HTTP {response.status_code}）"
    return success, str(message)


@router.post("/delete")
async def delete_redeemed_card(request: RedeemDeleteRequest) -> Response:
    external_code = normalize_redeem_code(request.code)
    if not external_code:
        raise HTTPException(status_code=400, detail="卡密格式无效")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            external_response = await client.post(
                THIRD_PARTY_DELETE_URL,
                headers=third_party_headers(),
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


@router.post("/delete/batch")
async def batch_delete_redeemed_cards(request: RedeemBatchDeleteRequest) -> dict:
    semaphore = asyncio.Semaphore(request.concurrency)

    # 去掉供应商后缀后再次去重，避免 abc 与 abc-4513 重复请求同一张卡密。
    prepared_codes = []
    seen_external_codes = set()
    for original_code in request.codes:
        external_code = normalize_redeem_code(original_code)
        if external_code not in seen_external_codes:
            prepared_codes.append((original_code, external_code))
            seen_external_codes.add(external_code)

    async with httpx.AsyncClient(timeout=30.0) as client:
        async def delete_one(original_code: str, external_code: str) -> dict:
            if not external_code:
                return {
                    "code": original_code,
                    "success": False,
                    "message": "卡密格式无效",
                }

            try:
                async with semaphore:
                    response = await client.post(
                        THIRD_PARTY_DELETE_URL,
                        headers=third_party_headers(),
                        json={"code": external_code},
                    )
                success, message = third_party_result(response)
                return {
                    "code": original_code,
                    "success": success,
                    "message": message,
                }
            except httpx.TimeoutException:
                return {
                    "code": original_code,
                    "success": False,
                    "message": "第三方删除接口请求超时",
                }
            except httpx.HTTPError as exc:
                return {
                    "code": original_code,
                    "success": False,
                    "message": f"第三方删除接口请求失败: {exc}",
                }

        items = await asyncio.gather(
            *(delete_one(original, external) for original, external in prepared_codes)
        )

    success_count = sum(1 for item in items if item["success"])
    failed_count = len(items) - success_count
    return {
        "success": True,
        "message": f"批量删除完成：成功 {success_count}，失败 {failed_count}",
        "data": {
            "total": len(items),
            "success_count": success_count,
            "failed_count": failed_count,
            "items": items,
        },
    }
