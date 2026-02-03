import httpx
import re
from typing import Dict, Any
from datetime import datetime, timedelta, timezone

LCARD_API_URL = "http://a.card4399.top/api.php"

async def redeem_lcard_key(card_key: str) -> Dict[str, Any]:
    """
    激活 LCard 卡密
    API: http://a.card4399.top/api.php?action=query&card_keys=XXX
    """
    # 移除 -L 后缀
    real_key = card_key.replace("-L", "").strip()

    params = {
        "action": "query",
        "card_keys": real_key
    }

    print(f"[LCard] Querying key: {real_key}")

    async with httpx.AsyncClient() as client:
        try:
            print(f"[LCard] Request URL: {LCARD_API_URL}?{client.build_request('GET', LCARD_API_URL, params=params).url.query.decode('utf-8')}")
            
            # 尝试 GET 请求 (根据 PHP API 惯例)
            response = await client.get(LCARD_API_URL, params=params, timeout=30.0)
            
            print(f"[LCard] Response Status: {response.status_code}")
            # print(f"[LCard] Raw Response: {response.text}") # 调试用，生产环境可注释

            # 解析 JSON
            try:
                data = response.json()
                print(f"[LCard] Parsed JSON: {data}")
            except Exception:
                # 某些 PHP error 可能会返回 text/html
                print(f"[LCard] Invalid JSON Response: {response.text[:200]}")
                return {"success": False, "error": f"Invalid JSON response: {response.text[:100]}"}
            
            # 确定目标结果对象
            target_result = None
            
            # 情况1: 直接返回列表 (User Case)
            if isinstance(data, list):
                if len(data) > 0:
                    # 尝试优先匹配传入的 card_key
                    target_result = next((item for item in data if item.get("card_key") == real_key), data[0])
            
            # 情况2: 返回字典结构
            elif isinstance(data, dict):
                # 检查 results 字段
                if isinstance(data.get("results"), list) and len(data["results"]) > 0:
                    target_result = data["results"][0]
                # 检查是否有 success: true 且 data 字段
                elif data.get("success") and isinstance(data.get("data"), list) and len(data["data"]) > 0:
                    target_result = data["data"][0]
                # 本身可能就是结果对象
                elif "activation_code" in data:
                    target_result = data

            # 处理提取到的结果
            if target_result:
                print(f"[LCard] Processing result: {target_result}")
                
                # 解析 activation_code
                activation_code = target_result.get("activation_code", "")
                
                # 处理 created_at (时区转换: UTC -> China Time)
                raw_created = target_result.get("created_at", "")
                created_iso = ""
                expire_iso = None
                
                if raw_created:
                    try:
                        # 清理格式，假设 API 返回 "YYYY-MM-DD HH:MM:SS"
                        clean_time = raw_created.replace("T", " ").split(".")[0]
                        
                        # 假设 API 返回的是 UTC-4 时间 (根据用户反馈 05:42 -> 17:42，相差 12 小时 (-4 -> +8))
                        dt_server = datetime.strptime(clean_time, "%Y-%m-%d %H:%M:%S")
                        dt_server = dt_server.replace(tzinfo=timezone(timedelta(hours=-4)))
                        
                        # 转为中国时区 (UTC+8)
                        china_tz = timezone(timedelta(hours=8))
                        dt_cn = dt_server.astimezone(china_tz)
                        created_iso = dt_cn.isoformat()
                        
                        # 计算 24 小时过期时间 (基于中国时区时间)
                        dt_exp = dt_cn + timedelta(hours=24)
                        expire_iso = dt_exp.isoformat()
                        
                    except Exception as e:
                        print(f"[LCard] Date parse error ({raw_created}): {e}")
                        if " " in raw_created:
                            created_iso = raw_created.replace(" ", "T")
                        else:
                            created_iso = raw_created

                # 构建标准化的响应结构
                normalized_data = {
                    "success": True,  # 只要拿到了数据，视为 API 调用成功
                    "original_result": target_result,
                    "card_key": target_result.get("card_key") or real_key,
                    "created_time": created_iso,
                    "expire_time": expire_iso, # 传递计算好的过期时间给 activation.py
                    "validity_hours": 24, # 保持24小时
                    "lcard_status_text": target_result.get("status_text")
                }
                
                # 提取卡号、日期、CVV
                if activation_code:
                    # 卡号
                    card_match = re.search(r"卡号[:：]\s*(\d+)", activation_code)
                    print(f"[LCard] Card Match: {card_match}")
                    if card_match:
                        normalized_data["pan"] = card_match.group(1)
                        print(f"[LCard] Extracted PAN: {normalized_data['pan']}")

                    # CVV
                    cvv_match = re.search(r"CVV[:：]\s*(\d+)", activation_code)
                    print(f"[LCard] CVV Match: {cvv_match}")
                    if cvv_match:
                        normalized_data["cvv"] = cvv_match.group(1)
                        
                    # 日期 (MM/YY)
                    date_match = re.search(r"日期[:：]\s*(\d{1,2}/\d{2})", activation_code)
                    print(f"[LCard] Date Match: {date_match}")
                    if date_match:
                        date_str = date_match.group(1)
                        parts = date_str.split('/')
                        if len(parts) == 2:
                            normalized_data["exp_month"] = parts[0].zfill(2)
                            normalized_data["exp_year"] = "20" + parts[1] # 假定 20xx
                
                print(f"[LCard] Final Normalized Data: {normalized_data}")
                return normalized_data
            
            # 未找到有效数据
            return {"success": False, "error": "No matching card data found", "raw": data}
            
        except Exception as e:
            print(f"[LCard] Error: {e}")
            return {"success": False, "error": f"Network Error: {str(e)}"}
