import httpx
from typing import Dict, Any, Optional

MERCURY_REDEEM_URL = "https://actcard.xyz/api/keys/redeem"
MERCURY_QUERY_URL = "https://actcard.xyz/api/keys/query"
MERCURY_TRANSACTIONS_URL = "https://actcard.xyz/api/keys/transactions"
AIRWALLEX_REDEEM_URL = "https://actcard.xyz/api/airwallex/redeem"

import re

# Airwallex 卡密格式: UUID-XXXX (如 ac1a0db7-7713-4ae0-979f-ceca2c9fc2e5-4513)，限制后缀长度为4
AIRWALLEX_KEY_PATTERN = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}-[0-9a-zA-Z]{4}$',
    re.IGNORECASE
)

def is_airwallex_key(key_id: str) -> bool:
    """判断是否为 Airwallex 格式卡密 (UUID-XXXX)"""
    return bool(AIRWALLEX_KEY_PATTERN.match(key_id.strip()))


def _get_headers() -> dict:
    """通用请求 headers"""
    return {
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9",
        "cache-control": "no-cache",
        "content-type": "application/json",
        "origin": "https://actcard.xyz",
        "priority": "u=1, i",
        "referer": "https://actcard.xyz/",
        "sec-ch-ua": '"Not(A:Brand";v="8", "Chromium";v="144", "Google Chrome";v="144"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
    }


async def redeem_key(key_id: str) -> Dict[str, Any]:
    """
    激活卡密 (Redeem Key) via Mercury API
    
    Args:
        key_id: The key ID to redeem.
        
    Returns:
        JSON response from the API.
    """
    headers = _get_headers()
    payload = {"key_id": key_id, "fallback_card_type": "debit"}

    # 解析可能存在的后缀格式 (如 UUID-520524)
    key_match = re.match(r'^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})-(.+)$', key_id.strip())
    if key_match:
        actual_key_id = key_match.group(1)
        suffix = key_match.group(2)
        # 带后缀时重置 payload，去掉 fallback_card_type 避免可能的 409 冲突
        payload = {
            "key_id": actual_key_id,
            "redeem_mode": f"{suffix}-gpt-plus-team"
        }

    async with httpx.AsyncClient() as client:
        # Step 1: Query the key status first
        try:
            query_response = await client.post(MERCURY_QUERY_URL, json=payload, headers=headers)
            query_data = query_response.json()
            
            # If success is True, it means the card is already active
            if query_data.get("success") is True:
                return query_data
                
            # If success is False and error is "卡密未使用" (Card unused), proceed to redeem
            if query_data.get("success") is False and query_data.get("error") == "卡密未使用":
                pass # Continue to redeem
            else:
                # If it's another error (e.g. invalid key), return the query result
                return query_data
                
        except Exception as e:
            print(f"Error checking key status: {e}")
            return {"success": False, "error": f"Network/Query Error: {str(e)}"}

        # Step 2: Redeem if unused
        response = await client.post(MERCURY_REDEEM_URL, json=payload, headers=headers)
        return response.json()


async def redeem_airwallex_key(key_id: str) -> Dict[str, Any]:
    """
    激活 Airwallex 格式卡密
    格式: UUID-XXXX (如 ac1a0db7-7713-4ae0-979f-ceca2c9fc2e5-4513)
    接口: https://actcard.xyz/api/airwallex/redeem
    
    Args:
        key_id: Airwallex 格式的卡密
        
    Returns:
        JSON response from the API.
    """
    headers = _get_headers()
    
    # 去掉后缀，只保留纯 UUID 部分 (如 ac1a0db7-7713-4ae0-979f-ceca2c9fc2e5-4513 -> ac1a0db7-7713-4ae0-979f-ceca2c9fc2e5)
    code = key_id.rsplit("-", 1)[0]
    payload = {"code": code}

    async with httpx.AsyncClient() as client:
        try:
            print(f"[Airwallex] POST {AIRWALLEX_REDEEM_URL} payload: {payload}")
            response = await client.post(AIRWALLEX_REDEEM_URL, json=payload, headers=headers)
            return response.json()
        except Exception as e:
            print(f"[Airwallex] 请求失败: {e}")
            return {"success": False, "error": f"Network Error: {str(e)}"}


async def get_key_transactions(key_id: str) -> Dict[str, Any]:
    """
    查询卡密交易记录
    
    Args:
        key_id: The key ID to query transactions for.
        
    Returns:
        JSON response from the API containing transaction records.
    """
    headers = _get_headers()
    
    # 解析并移除可能存在的后缀，仅使用实际的 UUID 进行查询
    key_match = re.match(r'^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})-(.+)$', key_id.strip())
    if key_match:
        key_id = key_match.group(1)
        
    payload = {"key_id": key_id}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(MERCURY_TRANSACTIONS_URL, json=payload, headers=headers)
            data = response.json()
            
            # 如果请求失败或success为false, 直接返回
            if not data.get("success"):
                return data
                
            # Normalize transactions to match system format
            # 用户指定映射:
            # 支付额度: amount
            # 支付状态: status
            # 支付备注: reason_for_failure
            
            normalized_txs = []
            for tx in data.get("transactions", []):
                normalized_txs.append({
                    # Standard fields expected by frontend/system
                    "merchant": tx.get("merchant_name") or tx.get("bank_description"),
                    "amount": tx.get("amount"),
                    "currency": tx.get("merchant_currency"),
                    "date": tx.get("created_at"),
                    "status": tx.get("status"),
                    "failureReason": tx.get("reason_for_failure"), # Mapped as requested
                    "id": tx.get("id"),
                    
                    # Store original fields as well if needed
                    "original_amount": tx.get("amount"),
                    "original_status": tx.get("status"),
                    "bank_description": tx.get("bank_description")
                })
            
            return {
                "success": True,
                "transactions": normalized_txs,
                "transaction_count": data.get("transaction_count", 0),
                "card_id": data.get("card_id"),
                "account_user_id": data.get("account_user_id"),
                # 保留原始数据以防万一
                "original_response": data
            }

        except Exception as e:
            print(f"Error fetching transactions: {e}")
            return {"success": False, "error": f"Network Error: {str(e)}"}

if __name__ == "__main__":
    import asyncio
    
    async def main():
        # Example usage
        try:
            # key_id = "5236c9bd-f11f-45b7-8d21-29bef978ca2f"
            # print(f"Checking transactions for key: {key_id}")
            # res = await get_key_transactions(key_id)
            # print(res)
            pass
        except Exception as e:
            print(f"Error: {e}")

    asyncio.run(main())
