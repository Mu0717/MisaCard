"""
NodeCard 卡密激活模块
API: https://api.node-card.com/api/card/issue
"""
import httpx
from typing import Dict, Any

NODECARD_API_URL = "https://api.node-card.com/api/open/card/redeem"


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
    # 移除 -node 后缀，提取真正的 card_key
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
        "card_key": real_key
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
                exp = card_data.get("exp", "")
                exp_month = ""
                exp_year = ""
                if "/" in exp:
                    parts = exp.split("/")
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
                    "created_time": card_data.get("redeem_time"),
                    "expire_time": card_data.get("expire_time"),
                    # 有效时长
                    "validity_hours": card_data.get("available_hours"),
                    # 余额 (单位: USD)
                    "balance": card_data.get("available_amount"),
                    # 完整账单地址 (API 返回单字符串)
                    "full_billing_address": card_data.get("full_billing_address", ""),
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


NODECARD_TRANSACTIONS_URL = "https://api.node-card.com/api/open/card/transactions"


def _parse_amount(amount_str) -> tuple:
    """
    解析金额字符串，兼容 "0 USD"、"10.5 USD" 等格式。
    返回 (amount_float, currency_str)
    """
    if isinstance(amount_str, (int, float)):
        return float(amount_str), "USD"
    if isinstance(amount_str, str):
        parts = amount_str.strip().split()
        try:
            amount = float(parts[0])
        except (ValueError, IndexError):
            amount = 0.0
        currency = parts[1] if len(parts) > 1 else "USD"
        return amount, currency
    return 0.0, "USD"


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
        "Content-Type": "application/json;charset=utf-8",
        "Accept": "application/json;charset=utf-8",
        "Origin": "https://node-card.com",
        "Referer": "https://node-card.com/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
    }

    payload = {"card_key": real_key}

    async with httpx.AsyncClient() as client:
        try:
            print(f"[NodeCard] 查询交易记录: {real_key}")
            response = await client.post(
                NODECARD_TRANSACTIONS_URL,
                json=payload,
                headers=headers,
                timeout=30.0
            )

            print(f"[NodeCard] 交易记录响应状态码: {response.status_code}")
            data = response.json()
            print(f"[NodeCard] 交易记录响应: {data}")

            if data.get("code") == 1 and isinstance(data.get("data"), dict):
                raw_txs = data["data"].get("transactions", [])

                # 标准化交易记录格式 (字段名与 API 实际返回一致)
                normalized_txs = []
                for tx in raw_txs:
                    amt, currency = _parse_amount(tx.get("amount"))
                    normalized_txs.append({
                        "merchant": tx.get("merchant"),
                        "amount": amt,
                        "currency": currency,
                        "date": tx.get("date"),
                        "status": tx.get("status"),
                        "failureReason": tx.get("failureReason") if tx.get("failureReason") != "APPROVED" else None,
                        "id": tx.get("id"),
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
