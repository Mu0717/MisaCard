import httpx
import re
from typing import Dict, Any
from datetime import datetime, timedelta, timezone

LCARD_API_URL = "https://vc7777.cn/api.php"

async def redeem_lcard_key(card_key: str) -> Dict[str, Any]:
    """
    激活 LCard 卡密
    API: https://vc7777.cn/api.php
    """
    # 移除 -L 后缀
    real_key = card_key.replace("-L", "").strip()

    print(f"[LCard] Querying key: {real_key}")

    async with httpx.AsyncClient() as client:
        try:
            print(f"[LCard] Request URL: {LCARD_API_URL} (POST)")
            
            # 使用 multipart/form-data 发送 POST 请求，与浏览器中表单提交格式一致
            form_data = {
                "action": (None, "query"),
                "card_keys": (None, real_key)
            }
            
            response = await client.post(LCARD_API_URL, files=form_data, timeout=30.0)
            
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
                
                raw_created = target_result.get("created_at", "")
                raw_used = target_result.get("used_at", "")
                
                created_iso = None
                expire_iso = None

                # 因为前端在 activate.html 不可修改，且存在 new Date(xx) + 减去1小时 的奇特时区机制
                # 要让前端最后显示的时间（即 new Date(xx) + 8小时时区 - 1小时 = xx + 7小时）恰好等于原始真实的接口中国时间
                # 就必须将字符串在 Python 后台减去 7 个小时，并包装成严格的 UTC 格式（携带 +00:00）。
                if raw_created:
                    try:
                        clean_time = raw_created.replace("T", " ").split(".")[0]
                        dt_server = datetime.strptime(clean_time, "%Y-%m-%d %H:%M:%S")
                        dt_compensate = dt_server - timedelta(hours=8)
                        created_iso = dt_compensate.strftime("%Y-%m-%dT%H:%M:%S.000Z")
                    except Exception as e:
                        created_iso = raw_created
                        
                if raw_used:
                    try:
                        clean_used = raw_used.replace("T", " ").split(".")[0]
                        dt_used = datetime.strptime(clean_used, "%Y-%m-%d %H:%M:%S")
                        dt_used_comp = dt_used - timedelta(hours=8)
                        expire_iso = dt_used_comp.strftime("%Y-%m-%dT%H:%M:%S.000Z")
                    except Exception as e:
                        expire_iso = raw_used
                        
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
                    # 适配多种分隔符格式：如 "---" 或 "----" 等（2个及以上连续短横线）
                    # 例: "5205245043938607---12/29---609" 或 "4859540130534455----2030-4----590"
                    if re.search(r'-{2,}', activation_code):
                        parts = [p.strip() for p in re.split(r'-{2,}', activation_code)]
                        if len(parts) >= 3:
                            normalized_data["pan"] = parts[0]
                            print(f"[LCard] Extracted PAN: {normalized_data['pan']}")
                            
                            date_str = parts[1] # 例如 "2030-4"、"2030/4"、"08/33"、"08-33"、"0529"
                            # 智能识别日期格式：先检查是否包含分隔符，再处理纯数字
                            sep = "-" if "-" in date_str else ("/" if "/" in date_str else None)
                            if sep:
                                part_a, part_b = date_str.split(sep, 1)
                                if len(part_a) == 4:
                                    # 格式: YYYY-M 或 YYYY/M（如 "2030-4"、"2030/4"）
                                    normalized_data["exp_year"] = part_a
                                    normalized_data["exp_month"] = part_b.zfill(2)
                                elif len(part_b) == 4:
                                    # 格式: M-YYYY 或 M/YYYY（如 "4-2030"、"4/2030"）
                                    normalized_data["exp_year"] = part_b
                                    normalized_data["exp_month"] = part_a.zfill(2)
                                elif len(part_a) <= 2 and len(part_b) <= 2:
                                    # 格式: MM/YY 或 MM-YY（如 "08/33"、"08-33"）
                                    normalized_data["exp_month"] = part_a.zfill(2)
                                    normalized_data["exp_year"] = "20" + part_b.zfill(2)
                                else:
                                    # 兜底：无法识别的格式，原样保留并记录日志
                                    normalized_data["exp_month"] = part_a.zfill(2)
                                    normalized_data["exp_year"] = part_b
                                    print(f"[LCard] 警告: 无法确定日期格式，原样保留: {date_str}")
                            elif date_str.isdigit():
                                # 纯数字格式，无分隔符
                                if len(date_str) == 4:
                                    # 格式: MMYY（如 "0529" → 05月/2029年）
                                    normalized_data["exp_month"] = date_str[:2]
                                    normalized_data["exp_year"] = "20" + date_str[2:]
                                elif len(date_str) == 3:
                                    # 格式: MYY（如 "529" → 5月/2029年）
                                    normalized_data["exp_month"] = date_str[:1].zfill(2)
                                    normalized_data["exp_year"] = "20" + date_str[1:]
                                elif len(date_str) == 6:
                                    # 格式: MMYYYY（如 "052029" → 05月/2029年）
                                    normalized_data["exp_month"] = date_str[:2]
                                    normalized_data["exp_year"] = date_str[2:]
                                else:
                                    # 兜底：无法识别的纯数字格式
                                    normalized_data["exp_month"] = date_str[:2].zfill(2)
                                    normalized_data["exp_year"] = date_str[2:] if len(date_str) > 2 else date_str
                                    print(f"[LCard] 警告: 无法确定纯数字日期格式，尝试拆分: {date_str}")
                            else:
                                # 兜底：非数字也非分隔符格式，原样记录
                                print(f"[LCard] 警告: 无法解析日期字段: {date_str}")
                            
                            normalized_data["cvv"] = parts[2]
                            print(f"[LCard] Extracted Date: {normalized_data.get('exp_year')}-{normalized_data.get('exp_month')}, CVV: {normalized_data.get('cvv')}")
                            
                            if len(parts) >= 4:
                                normalized_data["sms_url"] = parts[3]
                                print(f"[LCard] Extracted SMS URL: {normalized_data['sms_url']}")
                    else:
                        # 兼容旧格式提取
                        card_match = re.search(r"卡号[:：]\s*(\d+)", activation_code)
                        print(f"[LCard] Card Match: {card_match}")
                        if card_match:
                            normalized_data["pan"] = card_match.group(1)
                            print(f"[LCard] Extracted PAN: {normalized_data['pan']}")

                        cvv_match = re.search(r"CVV[:：]\s*(\d+)", activation_code)
                        print(f"[LCard] CVV Match: {cvv_match}")
                        if cvv_match:
                            normalized_data["cvv"] = cvv_match.group(1)
                            
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
