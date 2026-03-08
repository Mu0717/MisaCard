"""
ncetCard 卡密激活模块
"""
import httpx
import asyncio
import json
from typing import Dict, Any

NCETCARD_BASE_URL = "https://sd.ncet.top"


def is_ncetcard_key(card_key: str) -> bool:
    """
    判断是否为 ncetCard 卡密
    格式: 以 -NCET 结尾
    """
    return card_key.upper().endswith("-NCET")


async def redeem_ncetcard_key(card_key: str) -> Dict[str, Any]:
    """
    激活 ncetCard 卡密

    Args:
        card_key: 卡密 (可能含 -NCET 后缀)

    Returns:
        标准化的响应数据 (包含 success 字段)
    """
    # 提取真实的 code，如果存在 -NCET 后缀则截取
    code = card_key
    if code.upper().endswith("-NCET"):
        code = code[:-5]

    headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
        "Origin": NCETCARD_BASE_URL,
        "Referer": f"{NCETCARD_BASE_URL}/redeem",
    }

    async with httpx.AsyncClient() as client:
        try:
            print(f"[ncetCard] 1. 验证卡密: {code}")
            validate_url = f"{NCETCARD_BASE_URL}/shop/shop/redeem/validate?code={code}"
            val_resp = await client.get(validate_url, headers=headers, timeout=15.0)
            val_data = val_resp.json()
            print(f"[ncetCard] 验证响应: {val_data}")

            val_res_data = val_data.get("data", {})
            # 检查是否已经激活且存在卡片数据
            if val_data.get("code") == 200 and val_res_data.get("isUsed") is True and val_res_data.get("cards"):
                print(f"[ncetCard] 卡密已被使用，直接提取现存卡片信息")
                return _parse_ncetcard_data(val_res_data.get("cards")[0], val_data)

            if val_data.get("code") != 200 or not val_res_data.get("valid"):
                return {
                    "success": False,
                    "error": f"卡密验证失败: {val_data.get('message', '未知错误')}",
                    "original_response": val_data
                }

            print(f"[ncetCard] 2. 提交兑换请求: {code}")
            redeem_url = f"{NCETCARD_BASE_URL}/shop/shop/redeem"
            payload = {
                "code": code,
                "visitorId": None,
                "quantity": 1
            }
            redeem_resp = await client.post(redeem_url, json=payload, headers=headers, timeout=15.0)
            redeem_data = redeem_resp.json()
            print(f"[ncetCard] 兑换响应: {redeem_data}")

            if redeem_data.get("code") != 200:
                return {
                    "success": False,
                    "error": f"兑换失败: {redeem_data.get('message', '未知错误')}",
                    "original_response": redeem_data
                }

            order_no = redeem_data.get("data", {}).get("orderNo")
            if not order_no:
                return {
                    "success": False,
                    "error": "兑换成功但未返回订单号",
                    "original_response": redeem_data
                }

            print(f"[ncetCard] 3. 开始轮询订单状态, OrderNo: {order_no}")
            status_url = f"{NCETCARD_BASE_URL}/shop/shop/redeem/order-status/{order_no}"
            
            max_retries = 30
            card_info = None

            for i in range(max_retries):
                await asyncio.sleep(2)
                status_resp = await client.get(status_url, headers=headers, timeout=10.0)
                status_data = status_resp.json()
                print(f"[ncetCard] 轮询 {i+1}/{max_retries} 次响应: {status_data}")

                if status_data.get("code") == 200:
                    data = status_data.get("data", {})
                    cards = data.get("cards")
                    if cards and isinstance(cards, list) and len(cards) > 0:
                        card_info = cards[0]
                        break
                
            if not card_info:
                return {
                    "success": False,
                    "error": "轮询超时，未获取到卡片信息",
                    "original_response": redeem_data
                }

            print(f"[ncetCard] 获取到卡片信息: {card_info}")
            return _parse_ncetcard_data(card_info, status_data)

        except Exception as e:
            print(f"[ncetCard] 请求异常: {e}")
            return {"success": False, "error": f"Network Error: {str(e)}"}

def _format_time_with_tz(time_str: str) -> str:
    """如果日期没有时区信息，默认添加中国时区 (+08:00)"""
    if not time_str:
        return time_str
    if "Z" not in time_str and "+" not in time_str:
        return f"{time_str}+08:00"
    return time_str

def _parse_ncetcard_data(card_info: dict, original_response: dict) -> dict:
    """
    解析 ncetCard 的卡片数据字典
    """
    card_data_str = card_info.get("cardData", "{}")
    try:
        card_data_json = json.loads(card_data_str)
    except Exception as e:
        print(f"[ncetCard] 解析 cardData 失败: {e}")
        card_data_json = {}

    # 解析有效期 (例如: "0332" -> exp_month="03", exp_year="32")
    expiry = card_data_json.get("expiry", "")
    exp_month = ""
    exp_year = ""
    if expiry and len(expiry) >= 4:
        exp_month = expiry[:2]
        exp_year = expiry[2:4]

    # 构建标准化响应，供 activation.py 提取
    normalized = {
        "success": True,
        "card_type": "ncetcard",
        "pan": card_info.get("cardNumber"),
        "cvv": card_data_json.get("cvv") or card_info.get("cardPassword"),
        "exp_month": exp_month,
        "exp_year": "20" + exp_year if len(exp_year) == 2 else exp_year,
        "expire_time": _format_time_with_tz(card_data_json.get("expireTime")),
        "created_time": _format_time_with_tz(card_info.get("createTime")),
        "legal_address": {
            "address1": "7901 4th Street North",
            "city": "St. Petersburg",
            "region": "Florida",
            "postal_code": "78731",
            "country": "US"
        },
        "original_response": original_response
    }
    
    print(f"[ncetCard] 标准化数据: {normalized}")
    return normalized
