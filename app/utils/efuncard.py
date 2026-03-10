
import httpx
import re
from typing import Dict, Any, Optional
from datetime import datetime, timedelta, timezone

EFUNCARD_API_URL = "https://card.efuncard.com/api"
EFUNCARD_BILLING_ADDRESS = {
    "address1": "Unit 3, Enterprise House 260 Chorley New Road",
    "city": "Horwich, Bolton",
    "region": "England",
    "postal_code": "BL6 5NY",
    "country": "UK",
    "full": "Unit 3 , Enterprise House 260 Chorley New Road, Horwich, Bolton, England, BL6 5NY"
}

EFUNCARD_BILLING_ADDRESS_USA = {
    "address1": "1255 Woodland Shores",
    "city": "Osage Beach",
    "region": "MO",
    "postal_code": "65065",
    "country": "US",
    "full": "1255 Woodland Shores, Osage Beach, MO, 65065, United States"
}

EFUNCARD_BILLING_ADDRESS_CDK = {
    "address1": "107 Claymoor, Flora Street",
    "city": "Oldham",
    "region": "England",
    "postal_code": "OL1 2XG",
    "country": "UK",
    "full": "107 Claymoor, Flora Street, Oldham, England, OL1 2XG, UK"
}

def is_efuncard_key(coupon: str) -> bool:
    coupon_up = coupon.upper()
    return coupon_up.endswith("-EFUN") or "-EFUN" in coupon_up

async def redeem_efuncard_key(coupon: str) -> Dict[str, Any]:
    """
    Activate/Trade Efuncard coupon for card details using the /api/redeem endpoint.
    Requires CSRF token handling.
    If redeem fails with "already used", fallback to query API.
    """
    if coupon.upper().endswith("-EFUN"):
        coupon = coupon[:-5]

    base_url = "https://card.efuncard.com"
    redeem_url = "https://card.efuncard.com/api/redeem"
    
    print(f"[Efuncard] 开始激活: {coupon}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
        "Origin": base_url,
        "Referer": f"{base_url}/",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "sec-ch-ua": '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
    }

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            # 1. 访问首页获取 CSRF Token (Cookies)
            print("[Efuncard] 正在获取 CSRF Token...")
            try:
                page_resp = await client.get(base_url, headers=headers)
                csrf_token = client.cookies.get("csrf_token")
                
                if csrf_token:
                    print(f"[Efuncard] 获取到 CSRF Token: {csrf_token}")
                    headers["x-csrf-token"] = csrf_token
            except Exception as e:
                print(f"[Efuncard] 获取CSRF Token警告: {e}")

            # 2. 发起激活请求
            payload = {"code": coupon}
            response = await client.post(redeem_url, json=payload, headers=headers)
            print(f"[Efuncard] API响应 ({response.status_code}): {response.text}")

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
                    print(f"[Efuncard] 卡密已使用，尝试查询详情: {coupon}")
                    query_url = f"{base_url}/api/cards/query/{coupon}"
                    try:
                        query_resp = await client.get(query_url, headers=headers)
                        print(f"[Efuncard] 查询响应 ({query_resp.status_code}): {query_resp.text}")
                        query_json = query_resp.json()
                        if query_json.get("success") is True:
                            print("[Efuncard] 查询成功，使用查询结果")
                            resp_json = query_json
                            is_success = True
                    except Exception as ex:
                        print(f"[Efuncard] 查询异常: {ex}")

            if is_success:
                data = resp_json.get("data", {})
                
                # Address handling
                node_instructions = data.get("nodeInstructions", "") or data.get("usageInstructions", "")
                address_info = _parse_efuncard_address(node_instructions) or _parse_cdk_address(node_instructions)
                
                if not address_info:
                    if coupon.startswith("US-") or coupon.endswith("-USA"):
                        address_info = EFUNCARD_BILLING_ADDRESS_USA
                    else:
                        address_info = EFUNCARD_BILLING_ADDRESS

                # Expiry handling
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
                    "efuncard_original": data
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

def _parse_efuncard_address(text: str) -> Optional[Dict[str, str]]:
    """
    Parse address from Efuncard comma-separated nodeInstructions.
    Example: 6885 South Redwood Road, 306, West Jordan, UT, 84084, US
    """
    if not text:
        return None
        
    try:
        parts = [p.strip() for p in text.split(',') if p.strip()]
        if len(parts) >= 5:
            country = parts[-1]
            postal_code = parts[-2]
            region = parts[-3]
            city = parts[-4]
            address1 = ", ".join(parts[:-4])
            
            return {
                "address1": address1,
                "city": city,
                "region": region,
                "postal_code": postal_code,
                "country": country,
                "full": text
            }
    except Exception:
        pass
        
    return None

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

async def verify_3ds_code(last_four: str) -> Dict[str, Any]:
    """
    Check 3DS verification code for a card.
    API: https://card.efuncard.com/api/3ds/verify
    POST {"lastFour": "9598"}
    """
    url = "https://card.efuncard.com/api/3ds/verify"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://card.efuncard.com/",
        "Origin": "https://card.efuncard.com",
        "Content-Type": "application/json"
    }
    
    payload = {
        "lastFour": last_four
    }
    
    print(f"[Efuncard] Checking 3DS code for last 4: {last_four}")
    
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
            # First ensure we have a session/CSRF token if needed, 
            # effectively just making the request might work if API is public or handles it.
            # But based on user log, it has csrf_token.
            # Let's try to get CSRF token first similar to _redeem_efuncard_new if simple request fails?
            # Actually, let's try to get CSRF first to be safe, as the user provided log shows X-CSRF-Token.
            
            # 1. Visit home to get CSRF
            try:
                await client.get("https://card.efuncard.com/", headers=headers)
                csrf_token = client.cookies.get("csrf_token")
                if csrf_token:
                    headers["x-csrf-token"] = csrf_token
                    # Update cookie in headers if needed, but client session holds it.
            except Exception as e:
                print(f"[Efuncard] Warning fetching CSRF for 3ds: {e}")

            response = await client.post(url, json=payload, headers=headers)
            print(f"[Efuncard] 3DS Response: {response.text}")
            
            status = response.status_code
            if status != 200:
                return {
                    "success": False,
                    "error": f"HTTP {status}"
                }
                
            return response.json()
            
    except Exception as e:
        print(f"[Efuncard] 3DS Verify Error: {e}")
        return {
            "success": False,
            "error": str(e)
        }


async def get_efuncard_transactions(card_id_or_token: str) -> Dict[str, Any]:
    """
    Query transaction records for Efuncard (CDK/LR) cards.
    API: https://card.efuncard.com/api/cards/transactions/{card_id}
    """
    url = f"https://card.efuncard.com/api/cards/transactions/{card_id_or_token}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://card.efuncard.com/",
        "Origin": "https://card.efuncard.com"
    }
    
    print(f"[Efuncard] Querying transactions for: {card_id_or_token}")
    
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
            # Try to get CSRF first
            try:
                await client.get("https://card.efuncard.com/", headers=headers)
                csrf_token = client.cookies.get("csrf_token")
                if csrf_token:
                    headers["x-csrf-token"] = csrf_token
            except Exception:
                pass

            response = await client.get(url, headers=headers)
            print(f"[Efuncard] Transactions Response ({response.status_code}): {response.text[:200]}...")
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}"
                }
                
            resp_json = response.json()
            if not resp_json.get("success"):
                return {
                    "success": False,
                    "error": resp_json.get("message") or "Query failed"
                }

            data = resp_json.get("data", {})
            transactions = data.get("transactions", [])
            
            # Normalize transactions
            normalized_txs = []
            for tx in transactions:
                # Format: 2026-02-03T13:11:16.481+0000
                tx_date = tx.get("date")
                
                normalized_txs.append({
                    "merchant": tx.get("merchantName"),
                    "amount": tx.get("amount"),
                    "currency": tx.get("currency"),
                    "date": tx_date,
                    "status": tx.get("status"),
                    "failureReason": tx.get("failureReason"),
                    "id": tx.get("id")
                })

            return {
                "success": True,
                "card_number": f"****{data.get('lastFour')}" if data.get("lastFour") else None,
                "last_four": data.get("lastFour"),
                "transactions": normalized_txs,
                "total_count": data.get("total", 0),
                "settled_count": data.get("settledCount", 0),
                "settled_amount": data.get("settledAmount", 0)
            }

    except Exception as e:
        print(f"[Efuncard] Transaction Query Error: {e}")
        return {
            "success": False,
            "error": str(e)
        }
