
import httpx
import re
from typing import Dict, Any, Optional

VOCARD_API_URL = "https://vocard.store/user/api/order/trade"
VOCARD_BILLING_ADDRESS = {
    "address1": "Unit 3, Enterprise House 260 Chorley New Road",
    "city": "Horwich, Bolton",
    "region": "England",
    "postal_code": "BL6 5NY",
    "country": "UK",
    "full": "Unit 3 , Enterprise House 260 Chorley New Road, Horwich, Bolton, England, BL6 5NY"
}

async def redeem_vocard_key(coupon: str) -> Dict[str, Any]:
    """
    Activate/Trade Vocard coupon for card details.
    
    Args:
        coupon: The coupon code (e.g. LR-xxxx)
        
    Returns:
        Dict containing activation result and card details normalized for the system.
    """
    # 默认参数
    data = {
        "contact": "",
        "password": "",
        "coupon": coupon,
        "captcha": "",
        "num": "1",
        "item_id": "59",
        "pay_id": "1",
        "device": "0"
    }

    print(f"[Vocard] 开始激活: {coupon}")
    
    headers = {
        "Cookie": "USER_SESSION=ZXlKMGVYQWlPaUpLVjFRaUxDSjFhV1FpT2pFeE9UVXNJbUZzWnlJNklraFRNalUySW4wLmV5SmxlSEJwY21VaU9qRTRNREF3TURBM016WXNJbXh2WjJsdVZHbHRaU0k2SWpJd01qWXRNREV0TVRVZ01UWTZNVEk2TVRZaWZRLndOcjU3UFFWRVFaRF9pbzhSVURKWk9rY0c4aGZVZkdZMno1dS1keUpzbEE%3D; ACG-SHOP=gase7jcmokft2o19db5l0pmduj",
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
                        # 注入固定账单地址
                        "legal_address": VOCARD_BILLING_ADDRESS,
                        "billing_address_full": VOCARD_BILLING_ADDRESS["full"],
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
