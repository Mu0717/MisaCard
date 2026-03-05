"""
NodeCard 卡密激活模块
API: https://api.node-card.com/api/card/issue
"""
import httpx
from typing import Dict, Any

NODECARD_API_URL = "https://api.node-card.com/api/card/issue"


def is_nodecard_key(card_key: str) -> bool:
    """
    判断是否为 NodeCard 卡密
    格式: UUID-node (例如 e3757e77-caf3-4d5e-9461-c55694ef806e-node)
    """
    return card_key.lower().endswith("-node")


async def redeem_nodecard_key(card_key: str) -> Dict[str, Any]:
    """
    激活 NodeCard 卡密

    Args:
        card_key: 卡密 (含 -node 后缀)

    Returns:
        标准化的响应数据 (包含 success 字段)
    """
    # 移除 -node 后缀，提取真正的 secret
    real_key = card_key
    if real_key.lower().endswith("-node"):
        real_key = real_key[:-5]  # 移除 "-node" (5个字符)

    headers = {
        "Content-Type": "application/json;charset=utf-8",
        "Accept": "application/json;charset=utf-8",
        "Origin": "https://node-card.com",
        "Referer": "https://node-card.com/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
    }

    payload = {
        "secret": real_key,
        "merchantId": "1",
        "merchantName": "Google"
    }

    async with httpx.AsyncClient() as client:
        try:
            print(f"[NodeCard] 激活卡密: {real_key}")
            response = await client.post(
                NODECARD_API_URL,
                json=payload,
                headers=headers,
                timeout=30.0
            )

            print(f"[NodeCard] 响应状态码: {response.status_code}")
            data = response.json()
            print(f"[NodeCard] 响应数据: {data}")

            # NodeCard 的成功标志是 code == 1
            # code == 1 且 msg == "Card already in use" 也算成功（卡片已激活，返回信息）
            if data.get("code") == 1 and isinstance(data.get("data"), dict):
                card_data = data["data"]

                # 解析有效期 (格式: "03/29" -> exp_month="03", exp_year="29")
                expiry = card_data.get("expiry", "")
                exp_month = ""
                exp_year = ""
                if "/" in expiry:
                    parts = expiry.split("/")
                    if len(parts) == 2:
                        exp_month = parts[0]
                        exp_year = parts[1]

                # 构建标准化响应
                normalized = {
                    "success": True,
                    "card_type": "nodecard",
                    # 卡片基本信息 (扁平结构，与 LCard 类似)
                    "pan": card_data.get("card_number"),
                    "cvv": card_data.get("cvv"),
                    "exp_month": exp_month,
                    "exp_year": exp_year,
                    # 时间信息 (Unix 时间戳)
                    "created_time": card_data.get("exchange_time"),
                    "expire_time": card_data.get("expire_time"),
                    # 有效时长
                    "validity_hours": card_data.get("remaining_hours"),
                    # 余额
                    "balance": card_data.get("balance"),
                    # 地址信息 (构建为 legal_address 标准结构)
                    "legal_address": {
                        "address1": card_data.get("street_address", ""),
                        "city": card_data.get("city", ""),
                        "region": card_data.get("full_state", ""),
                        "postal_code": card_data.get("postal_code", ""),
                        "country": card_data.get("country", ""),
                    },
                    # 保留原始响应
                    "original_response": data,
                    "nodecard_msg": data.get("msg"),
                }

                print(f"[NodeCard] 标准化数据: {normalized}")
                return normalized

            # 失败情况
            error_msg = data.get("msg", "Unknown error")
            print(f"[NodeCard] 激活失败: {error_msg}")
            return {
                "success": False,
                "error": f"NodeCard 激活失败: {error_msg}",
                "original_response": data
            }

        except Exception as e:
            print(f"[NodeCard] 请求异常: {e}")
            return {"success": False, "error": f"Network Error: {str(e)}"}


NODECARD_TRANSACTIONS_URL = "https://api.node-card.com/api/card/getcardinfos"


async def get_nodecard_transactions(card_key: str) -> Dict[str, Any]:
    """
    查询 NodeCard 交易记录

    Args:
        card_key: 卡密 (可能含 -node 后缀)

    Returns:
        标准化的交易记录数据
    """
    # 移除 -node 后缀
    real_key = card_key
    if real_key.lower().endswith("-node"):
        real_key = real_key[:-5]

    headers = {
        "Accept": "application/json;charset=utf-8",
        "Origin": "https://node-card.com",
        "Referer": "https://node-card.com/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
    }

    params = {"secret": real_key}

    async with httpx.AsyncClient() as client:
        try:
            print(f"[NodeCard] 查询交易记录: {real_key}")
            response = await client.get(
                NODECARD_TRANSACTIONS_URL,
                params=params,
                headers=headers,
                timeout=30.0
            )

            print(f"[NodeCard] 交易记录响应状态码: {response.status_code}")
            data = response.json()
            print(f"[NodeCard] 交易记录响应: {data}")

            if data.get("code") == 1 and isinstance(data.get("data"), list):
                raw_txs = data["data"]

                # 标准化交易记录格式 (与 Vocard 保持一致)
                normalized_txs = []
                for tx in raw_txs:
                    normalized_txs.append({
                        "merchant": tx.get("merchant_name") or tx.get("content"),
                        "amount": tx.get("amount"),
                        "currency": "USD",
                        "date": tx.get("event_time"),
                        "status": tx.get("result"),
                        "failureReason": tx.get("result") if tx.get("result") != "APPROVED" else None,
                        "id": tx.get("event_id"),
                        "event_type": tx.get("event_type"),
                        "content": tx.get("content"),
                    })

                return {
                    "success": True,
                    "transactions": normalized_txs,
                    "total_count": len(normalized_txs),
                }

            # 失败
            error_msg = data.get("msg", "Unknown error")
            return {"success": False, "error": f"NodeCard 查询失败: {error_msg}"}

        except Exception as e:
            print(f"[NodeCard] 查询交易记录异常: {e}")
            return {"success": False, "error": f"Network Error: {str(e)}"}
