
import httpx
import re
from typing import Dict, Any, Optional
from datetime import datetime, timedelta, timezone

VOCARD_API_URL = "https://vocard.store/user/api/order/trade"
VOCARD_BILLING_ADDRESS = {
    "address1": "Unit 3, Enterprise House 260 Chorley New Road",
    "city": "Horwich, Bolton",
    "region": "England",
    "postal_code": "BL6 5NY",
    "country": "UK",
    "full": "Unit 3 , Enterprise House 260 Chorley New Road, Horwich, Bolton, England, BL6 5NY"
}

VOCARD_BILLING_ADDRESS_USA = {
    "address1": "1255 Woodland Shores",
    "city": "Osage Beach",
    "region": "MO",
    "postal_code": "65065",
    "country": "US",
    "full": "1255 Woodland Shores, Osage Beach, MO, 65065, United States"
}

VOCARD_BILLING_ADDRESS_CDK = {
    "address1": "107 Claymoor, Flora Street",
    "city": "Oldham",
    "region": "England",
    "postal_code": "OL1 2XG",
    "country": "UK",
    "full": "107 Claymoor, Flora Street, Oldham, England, OL1 2XG, UK"
}

async def redeem_vocard_key(coupon: str) -> Dict[str, Any]:
    """
    Activate/Trade Vocard coupon for card details.
    
    Args:
        coupon: The coupon code (e.g. LR-xxxx)
        
    Returns:
        Dict containing activation result and card details normalized for the system.
    """
    # 兼容新的 CDK 格式激活接口
    if coupon.startswith("CDK-"):
        return await _redeem_vocard_new(coupon)

    # 处理特殊后缀逻辑
    item_id = "59"
    final_coupon = coupon
    current_billing_address = VOCARD_BILLING_ADDRESS
    
    if coupon.endswith("-USA"):
        item_id = "61"
        final_coupon = coupon[:-4]  # 去掉 -USA 后缀
        current_billing_address = VOCARD_BILLING_ADDRESS_USA

    # 默认参数
    data = {
        "contact": "shaohua0717@gmail.com",
        "password": "",
        "coupon": final_coupon,
        "captcha": "",
        "num": "1",
        "item_id": item_id,
        "pay_id": "1",
        "device": "0"
    }

    print(f"[Vocard] 开始激活: {coupon}")
    
    headers = {
        # "Cookie": "ACG-SHOP=gase7jcmokft2o19db5l0pmduj; USER_SESSION=ZXlKMGVYQWlPaUpLVjFRaUxDSjFhV1FpT2pFeE9UVXNJbUZzWnlJNklraFRNalUySW4wLmV5SmxlSEJwY21VaU9qRTNOekU0TURnd05EUXNJbXh2WjJsdVZHbHRaU0k2SWpJd01qWXRNREV0TWpRZ01EZzZOVFE2TURRaWZRLmx5VXp5YUhYaTI5SWJnMnlnQ3ZIMi1INlV0bzIyOHhDMFY4aWdyNW5jd2c%3D",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(VOCARD_API_URL, data=data, headers=headers, timeout=30.0)
            
            # 记录原始响应以便调试
            print(f"[Vocard] API响应: {response.text}")
            
            try:
                resp_json = response.json()
            except Exception:
                return {
                    "success": False,
                    "error": f"API响应解析失败: {response.text[:100]}",
                    "raw_response": response.text
                }

            if resp_json.get("code") == 200:
                # 解析成功
                api_data = resp_json.get("data", {})
                secret = api_data.get("secret", "")
                
                # 解析 secret 字符串
                # 格式示例: "z015 4462220002632161 01 / 2029 504"
                parsed_card = _parse_vocard_secret(secret)
                
                if not parsed_card:
                    return {
                        "success": False,
                        "error": f"无法解析卡密信息: {secret}",
                        "raw_data": api_data
                    }

                # 构建符合系统标准的返回结构
                return {
                    "success": True,
                    "card": {
                        "pan": parsed_card["pan"],
                        "cvv": parsed_card["cvc"],
                        "exp_month": parsed_card["exp_month"],
                        "exp_year": parsed_card["exp_year"],
                        # 使用 UTC 时间 + 1小时，activation.py 会将其解析为 UTC 并转换为 CST (+8)，最终结果为 CST + 1小时
                        "expire_time": (datetime.now(timezone.utc) + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"),
                        # 注入固定账单地址
                        "legal_address": current_billing_address,
                        "billing_address_full": current_billing_address["full"],
                        # 其他元数据
                        "trade_no": api_data.get("tradeNo"),
                        "stock": api_data.get("stock")
                    },
                    # 原始数据
                    "vocard_original": api_data
                }
            else:
                return {
                    "success": False, 
                    "error": resp_json.get("msg", "未知错误"),
                    "code": resp_json.get("code")
                }

    except Exception as e:
        return {
            "success": False,
            "error": f"请求异常: {str(e)}"
        }

def _parse_vocard_secret(secret: str) -> Optional[Dict[str, str]]:
    """
    解析 Secret 字符串
    示例: "z015 4462220002632161 01 / 2029 504"
    期望: 卡号 16位，日期 MM/YYYY，CVC 3位
    """
    if not secret:
        return None
        
    # 提取 PAN (16位数字)
    pan_match = re.search(r'\b(\d{16})\b', secret)
    pan = pan_match.group(1) if pan_match else ""
    
    # 提取日期 MM/YYYY 或 MM / YYYY
    date_match = re.search(r'(\d{1,2})\s*/\s*(\d{4})', secret)
    exp_month = "00"
    exp_year = "0000"
    date_str = ""
    
    if date_match:
        exp_month = date_match.group(1).zfill(2)
        exp_year = date_match.group(2)
        date_str = date_match.group(0) # 用于后续移除
        
    if not pan:
        # 如果连卡号都找不到，视为解析失败
        return None

    # 提取 CVC
    # 策略：从原字符串中移除 PAN 和 Date，剩下的如果是3-4位数字，则是 CVC
    cleaned = secret
    if pan:
        cleaned = cleaned.replace(pan, " ")
    if date_str:
        cleaned = cleaned.replace(date_str, " ")
        
    # 查找剩余的 3-4 位数字
    # 注意：z015 中的 015 可能会被匹配，如果它被单独分割。
    # z015 是一个单词，\b 会避免匹配内部
    cvc_candidates = re.findall(r'\b(\d{3,4})\b', cleaned)
    
    cvc = ""
    if cvc_candidates:
        # 通常 CVC 在最后，取最后一个候选
        cvc = cvc_candidates[-1]
        
    return {
        "pan": pan,
        "cvc": cvc,
        "exp_month": exp_month,
        "exp_year": exp_year
    }

async def _redeem_vocard_new(coupon: str) -> Dict[str, Any]:
    """
    Handle activation for new CDK format coupons.
    API: https://vocard.store/api/redeem
    Requires CSRF token handling.
    If redeem fails with "already used", fallback to query API.
    """
    base_url = "https://vocard.store"
    redeem_url = "https://vocard.store/api/redeem"
    
    print(f"[Vocard] 开始激活 (New API): {coupon}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Origin": base_url,
        "Referer": f"{base_url}/"
    }

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            # 1. 访问首页获取 CSRF Token (Cookies)
            print("[Vocard] 正在获取 CSRF Token...")
            try:
                page_resp = await client.get(base_url, headers=headers)
                csrf_token = client.cookies.get("csrf_token")
                
                if csrf_token:
                    print(f"[Vocard] 获取到 CSRF Token: {csrf_token}")
                    headers["x-csrf-token"] = csrf_token
            except Exception as e:
                print(f"[Vocard] 获取CSRF Token警告: {e}")

            # 2. 发起激活请求
            payload = {"code": coupon}
            response = await client.post(redeem_url, json=payload, headers=headers)
            print(f"[Vocard] API响应 ({response.status_code}): {response.text}")

            try:
                resp_json = response.json()
            except Exception:
                return {
                    "success": False, 
                    "error": f"API响应解析失败 (Status {response.status_code}): {response.text[:100]}",
                    "raw_response": response.text
                }
            
            # 3. 逻辑判断与降级查询
            is_success = resp_json.get("success") is True
            
            if not is_success:
                error_msg = resp_json.get("error") or resp_json.get("message") or resp_json.get("msg") or ""
                # 如果提示已使用，尝试查询详情
                if "已使用" in str(error_msg) or "used" in str(error_msg).lower():
                    print(f"[Vocard] 卡密已使用，尝试查询详情: {coupon}")
                    query_url = f"{base_url}/api/cards/query/{coupon}"
                    try:
                        query_resp = await client.get(query_url, headers=headers)
                        print(f"[Vocard] 查询响应 ({query_resp.status_code}): {query_resp.text}")
                        query_json = query_resp.json()
                        if query_json.get("success") is True:
                            print("[Vocard] 查询成功，使用查询结果")
                            resp_json = query_json
                            is_success = True
                    except Exception as ex:
                        print(f"[Vocard] 查询异常: {ex}")

            if is_success:
                data = resp_json.get("data", {})
                
                # Address handling
                usage_instructions = data.get("usageInstructions", "")
                address_info = _parse_cdk_address(usage_instructions)
                if not address_info:
                    address_info = VOCARD_BILLING_ADDRESS_CDK

                # Expiry handling
                # autoCancelAt: "2026-01-29T10:10:27.996Z" -> need "YYYY-MM-DD HH:MM:SS"
                auto_cancel = data.get("autoCancelAt")
                expire_time_str = ""
                if auto_cancel and "T" in auto_cancel:
                    # Remove Z, replace T with space, take up to seconds
                    expire_time_str = auto_cancel.replace("T", " ").replace("Z", "").split(".")[0]
                else:
                    # Default +1 hour
                    expire_time_str = (datetime.now(timezone.utc) + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")

                return {
                    "success": True,
                    "card": {
                        "pan": data.get("cardNumber"),
                        "cvv": data.get("cvv"),
                        "exp_month": str(data.get("expiryMonth", "")).zfill(2),
                        "exp_year": str(data.get("expiryYear", "")),
                        "expire_time": expire_time_str,
                        "legal_address": address_info,
                        "billing_address_full": address_info["full"],
                        "trade_no": str(data.get("cardId", "")),
                        "stock": "1"
                    },
                    "vocard_original": data
                }
            else:
                 return {
                    "success": False,
                    "error": resp_json.get("message") or resp_json.get("error", "激活失败"),
                    "code": resp_json.get("code")
                }

    except Exception as e:
        return {
            "success": False,
            "error": f"请求异常: {str(e)}"
        }

def _parse_cdk_address(text: str) -> Optional[Dict[str, str]]:
    """
    Parse address from usage instructions.
    Example: ... 卡片地址\n街道 107 Claymoor, Flora Street, 城市 Oldham, State England, 邮编 OL1 2XG, 英国
    """
    if not text:
        return None
        
    try:
        # Simple regex based on markers
        street_match = re.search(r'街道\s+(.*?),\s*城市', text)
        city_match = re.search(r'城市\s+(.*?),\s*State', text)
        state_match = re.search(r'State\s+(.*?),\s*邮编', text)
        zip_match = re.search(r'邮编\s+(.*?),\s*(.*)$', text, re.MULTILINE)
        
        if street_match and city_match:
            street = street_match.group(1).strip()
            city = city_match.group(1).strip()
            region = state_match.group(1).strip() if state_match else ""
            postal_code = ""
            country = "UK" # Default
            
            # Zip and Country might be mixed at end
            if zip_match:
                postal_code = zip_match.group(1).strip()
                last_part = zip_match.group(2).strip()
                if last_part:
                     country = last_part

            full = f"{street}, {city}, {region}, {postal_code}, {country}"
            
            return {
                "address1": street,
                "city": city,
                "region": region,
                "postal_code": postal_code,
                "country": country,
                "full": full
            }
    except Exception:
        pass
        
    return None
