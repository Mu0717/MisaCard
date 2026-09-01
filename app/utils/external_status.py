"""卡密供应商识别与远程状态查询。"""
from datetime import datetime, timezone
import re
from typing import Any, Dict, Optional, Tuple

import httpx


NIKO_QUERY_URL = "https://actcard.xyz/api/keys/query"
NIKO_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def detect_card_provider(card_id: str) -> Optional[Dict[str, str]]:
    """根据卡密格式识别支持状态查询的供应商。"""
    normalized = card_id.strip()
    if NIKO_UUID_PATTERN.fullmatch(normalized):
        return {"id": "niko", "label": "Niko"}
    return None


def _parse_datetime(value: Any) -> Optional[datetime]:
    if value in (None, "", 0):
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tz=timezone.utc)
        text = str(value).strip()
        if text.isdigit():
            return datetime.fromtimestamp(int(text), tz=timezone.utc)
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except (TypeError, ValueError, OSError):
        return None


def _normalize_niko_status(card_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """把 Niko 响应转换为后台统一状态摘要。"""
    error = str(payload.get("error") or payload.get("message") or "").strip()
    card = payload.get("card") if isinstance(payload.get("card"), dict) else {}

    if payload.get("destroyed") is True or card.get("destroyed") is True:
        status = "deleted"
    elif payload.get("success") is True:
        status = "active"
    elif "未使用" in error:
        status = "inactive"
    elif "不存在" in error:
        status = "not_found"
    elif "过期" in error or "到期" in error:
        status = "expired"
    elif "销毁" in error:
        status = "deleted"
    else:
        status = "unknown"

    activation_time = _parse_datetime(
        payload.get("used_time")
        or card.get("used_time")
        or card.get("created_time")
    )
    exp_date = _parse_datetime(
        card.get("expire_time")
        or card.get("delete_date")
        or payload.get("expiresAt")
    )

    if status == "active" and exp_date and exp_date <= datetime.now(timezone.utc):
        status = "expired"

    return {
        "card_id": str(payload.get("key_id") or card_id),
        "provider": "niko",
        "provider_label": "Niko",
        "query_source": "remote",
        "remote_status": status,
        "remote_message": error or "远程查询成功",
        "status": status,
        "is_activated": status in {"active", "expired", "deleted"},
        "card_activation_time": activation_time,
        "exp_date": exp_date,
    }


async def query_external_card_status(
    card_id: str,
) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """
    识别供应商并调用对应的只读查询接口。

    返回 (是否完成查询, 统一状态数据, 错误信息)。业务状态（例如卡密未使用、
    卡密不存在）仍属于一次成功完成的查询；仅网络、协议或不支持的类型算失败。
    """
    provider = detect_card_provider(card_id)
    if not provider:
        return False, None, "暂不支持该格式卡密的远程状态查询"

    if provider["id"] == "niko":
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    NIKO_QUERY_URL,
                    json={"key_id": card_id.strip()},
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                        "Origin": "https://actcard.xyz",
                        "Referer": "https://actcard.xyz/",
                    },
                )
            try:
                payload = response.json()
            except ValueError:
                return False, None, f"Niko 查询接口返回了无效响应（HTTP {response.status_code}）"

            if not isinstance(payload, dict):
                return False, None, "Niko 查询接口返回格式不正确"

            return True, _normalize_niko_status(card_id, payload), None
        except httpx.TimeoutException:
            return False, None, "Niko 查询接口响应超时"
        except httpx.HTTPError as exc:
            return False, None, f"Niko 查询接口请求失败：{exc}"

    return False, None, f"供应商 {provider['label']} 暂未配置查询接口"
