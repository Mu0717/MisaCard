"""
卡片自动激活功能
使用新的 Mercury API (mercury.wxie.de)
"""
import httpx
from typing import Optional, Dict, Tuple
import json
import asyncio

from ..config import (
    ACTIVATION_MAX_RETRIES,
    ACTIVATION_RETRY_DELAY
)
from .mercury import redeem_key
from .holy import redeem_holy_key
from .vocard import redeem_vocard_key

async def query_card_from_api(card_id: str) -> Tuple[bool, Optional[Dict], Optional[str]]:
    """
    (旧接口占位/适配)
    由于新 API 仅提供了激活(Redeem)接口，查询操作暂时也映射为尝试激活/获取信息。
    注意：这可能会导致副作用（即查询时就执行了激活）。
    
    Args:
        card_id: 卡密

    Returns:
        (成功标志, 卡片数据, 错误信息)
    """
    print(f"\n{'='*60}")
    print(f"[查询卡片(映射为Redeem)] 卡密: {card_id}")
    
    # 直接复用激活逻辑
    return await activate_card_via_api(card_id)


async def activate_card_via_api(card_id: str, max_retries: int = None, retry_delay: int = None) -> Tuple[bool, Optional[Dict], Optional[str]]:
    """
    通过 Mercury API 激活卡片 (Redeem)

    Args:
        card_id: 卡密
        max_retries: (新接口通常不需要轮询，保留参数兼容)
        retry_delay: (保留参数兼容)

    Returns:
        (成功标志, API完整响应数据, 错误信息)
    """
    try:
        print(f"\n{'='*60}")
        print(f"[激活卡片] 开始调用 API: {card_id}")
        
        response_data = {}
        
        if card_id.endswith("-Cursor"):
            # HolyMasterCard (Cursor suffix)
            print(f"[激活卡片] 检测到 Cursor 标记，使用 Holy API")
            response_data = await redeem_holy_key(card_id)
        elif card_id.upper().startswith("LR-"):
            # Vocard
            print(f"[激活卡片] 检测到 LR- 前缀，使用 Vocard API")
            response_data = await redeem_vocard_key(card_id)
        else:
            # Default Mercury
            print(f"[激活卡片] 使用默认 Mercury API")
            response_data = await redeem_key(card_id)
        
        print(f"[激活卡片] 响应内容: {json.dumps(response_data, ensure_ascii=False, indent=2)}")
        print(f"{'='*60}\n")
        
        # 解析响应
        if isinstance(response_data, dict):
            # 优先判断 success 字段
            if response_data.get("success") is True:
                return True, response_data, None
            
            # 检查是否有显式错误
            if response_data.get("error"):
                return False, response_data, response_data.get("error")
                
            # 兜底：如果 response_data 里没有 success 也没有 error，但在以前逻辑里可能算成功？
            # 按照用户给的示例，success: true 是必须的
            return False, response_data, "激活失败: API返回 success != true"
            
        return False, None, "响应格式无法解析"

    except Exception as e:
        print(f"[激活卡片] 异常: {str(e)}")
        return False, None, f"激活失败: {str(e)}"


def is_card_activated(card_data: Dict) -> bool:
    """
    检查卡片是否已激活
    依据 Mercury API 响应: {"success": true, ...}
    """
    if not card_data:
        return False
    
    # 只要 success 为 True 即视为激活成功
    return card_data.get("success") is True


def is_card_unactivated(card_data: Dict) -> bool:
    return not is_card_activated(card_data)


async def auto_activate_if_needed(card_id: str) -> Tuple[bool, Optional[Dict], str]:
    """
    自动激活流程
    直接调用 Redeem 接口
    """
    print(f"\n{'*'*60}")
    print(f"[自动激活流程] 开始处理卡密: {card_id}")
    print(f"{'*'*60}")
    
    # 直接激活
    success, data, error = await activate_card_via_api(card_id)
    
    if success:
        return True, data, "激活成功"
    else:
        # 如果是因为已经激活过（例如卡片已被redeem），API会返回什么？
        # 假设如果失败就是失败
        return False, data, error or "激活失败"


def extract_card_info(api_response: Dict) -> Dict:
    """
    从 Mercury API 响应中提取卡片信息
    结构示例:
    {
      "card": {
        "account_email": "...",
        "account_user_id": "...",
        "card_id": "...",
        "card_limit": 1,
        "created_time": "...",
        "cvv": "689",
        "exp_month": "12",
        "exp_year": "2031",
        "expire_time": "...",
        "pan": "5236860118604513"
      },
      "expire_minutes": 120,
      "success": true
    }
    """
    from datetime import datetime, timedelta, timezone
    
    if not api_response:
        return {}
        
    info = {}
    
    # 提取 card 对象
    card_data = api_response.get("card", {})
    if not isinstance(card_data, dict):
        # 尝试直接从根节点取（兼容旧结构或防御性编程）
        card_data = api_response
        
    # 卡号 (pan / cardNumber)
    info["card_number"] = card_data.get("pan") or card_data.get("card_number") or card_data.get("cardNumber")
    
    # CVV (cvv / card_cvc)
    info["card_cvc"] = card_data.get("cvv") or card_data.get("card_cvc")
    
    # 有效期格式化 (MM/YY)
    # Mercury: exp_month, exp_year
    # Holy: expiryMonth, expiryYear
    exp_month = str(card_data.get("exp_month") or card_data.get("expiryMonth") or "")
    exp_year = str(card_data.get("exp_year") or card_data.get("expiryYear") or "")
    
    if exp_month and exp_year:
        # 确保月份是两位
        if len(exp_month) == 1:
            exp_month = "0" + exp_month
        # 确保年份是后两位
        if len(exp_year) == 4:
            exp_year = exp_year[-2:]
        info["card_exp_date"] = f"{exp_month}/{exp_year}"
    else:
        info["card_exp_date"] = card_data.get("card_exp_date")
        
    # 其他字段
    # 处理账单地址 (legal_address)
    # Holy 可能没有返回 legal_address
    legal_addr = api_response.get("legal_address") or card_data.get("legal_address")
    if legal_addr and isinstance(legal_addr, dict):
        # 构建格式化地址字符串
        parts = []
        if legal_addr.get("address1"): parts.append(legal_addr["address1"])
        if legal_addr.get("address2"): parts.append(legal_addr["address2"])
        if legal_addr.get("city"): parts.append(legal_addr["city"])
        if legal_addr.get("region"): parts.append(legal_addr["region"])
        if legal_addr.get("postal_code"): parts.append(legal_addr["postal_code"])
        
        info["billing_address"] = ", ".join(filter(None, parts))
        # 保存原始地址信息供前端精确显示/复制
        info["legal_address"] = legal_addr
    else:
        # 如果没有返回地址，需要区分是 Holy 还是 Mercury 的 Fallback
        # Holy 特征: card 对象中有 cardNumber (camelCase) 或 root 有 activationToken
        is_holy = "cardNumber" in card_data or "activationToken" in api_response
        
        if is_holy:
            # Holy 卡密默认地址 (Spain)
            info["billing_address"] = "120 Avenida Martínez Campos, Alcantarilla, MC, 30820, Spain"
            info["legal_address"] = {
                "address1": "120 Avenida Martínez Campos",
                "city": "Alcantarilla",
                "region": "MC",
                "postal_code": "30820",
                "country": "Spain"
            }
        else:
            # Mercury 默认地址 (US)
            info["billing_address"] = "41 Glenn Rd C23, East Hartford, CT 06118"
            info["legal_address"] = {
                "address1": "41 Glenn Rd C23",
                "city": "East Hartford",
                "region": "CT",
                "postal_code": "06118",
                "country": "US"
            }

    info["card_nickname"] = card_data.get("card_nickname") or card_data.get("nickname") or f"Card {info.get('card_number', '')[-4:] if info.get('card_number') else ''}"
    info["card_limit"] = card_data.get("card_limit", 0)
    info["status"] = "已激活" if api_response.get("success") else "unknown"
    
    # 定义中国时区
    china_tz = timezone(timedelta(hours=8))

    def convert_to_china_time(time_str: Optional[str]) -> Optional[str]:
        if not time_str:
            return None
        try:
            # 处理整数时间戳 (Holy: scheduledDeleteAt, createdAt are timestamps?)
            # User example: createdAt: "2026-01-15T08:27:56Z" (string)
            # scheduledDeleteAt: 1768469276 (int)
            if isinstance(time_str, (int, float)):
                 dt = datetime.fromtimestamp(time_str, timezone.utc)
                 dt_cst = dt.astimezone(china_tz)
                 return dt_cst.isoformat()

            # 处理可能带有的 Z 后缀
            if time_str.endswith('Z'):
                time_str = time_str.replace('Z', '+00:00')
            
            # 解析 ISO 格式
            dt = datetime.fromisoformat(time_str)
            
            # 如果没有时区信息，默认视为 UTC
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            
            # 转换为中国时区
            dt_cst = dt.astimezone(china_tz)
            return dt_cst.isoformat()
        except Exception as e:
            print(f"时间转换出错 ({time_str}): {e}")
            return str(time_str)

    # 激活时间匹配逻辑:
    # 1. Query接口返回 used_time (在根节点)
    # 2. Redeem接口返回 created_time (在 card 节点)
    # Holy: createdAt (in card node)
    raw_create_time = api_response.get("used_time") or card_data.get("created_time") or card_data.get("createdAt")
    info["create_time"] = convert_to_china_time(raw_create_time)
    
    # 计算 validity_hours
    expire_minutes = api_response.get("expire_minutes")
    if expire_minutes is not None:
        info["validity_hours"] = int(expire_minutes) / 60
    else:
        info["validity_hours"] = card_data.get("validity_hours")
        
    # 过期时间匹配逻辑:
    # 1. 优先使用 API 返回的 expire_time (两个接口都在 card 节点)
    # 2. 其次使用 delete_date
    # 3. Holy: scheduledDeleteAt (in card node) or expiresAt (in root)
    # 4. 最后尝试本地计算
    
    api_expire_time = (
        card_data.get("expire_time") or 
        card_data.get("delete_date") or 
        card_data.get("scheduledDeleteAt") or 
        api_response.get("expiresAt")
    )
    
    if api_expire_time:
         info["exp_date"] = convert_to_china_time(api_expire_time)
    else:
        # 计算系统过期时间 (这里视为激活时间 + expire_minutes)
        # 使用中国时区 (UTC+8)
        calculated_exp_date = None
        if expire_minutes is not None:
            try:
                # 使用当前时间作为激活时间
                dt = datetime.now(china_tz)
                
                # 加上过期分钟数
                exp_dt = dt + timedelta(minutes=int(expire_minutes))
                calculated_exp_date = exp_dt.isoformat()
            except Exception as e:
                print(f"计算过期时间出错: {e}")
                pass
        info["exp_date"] = calculated_exp_date
    
    return info


async def get_card_transactions(card_number: str) -> Tuple[bool, Optional[Dict], Optional[str]]:
    """
    查询交易记录
    目前 Mercury API 未提供明确的交易查询接口，暂时返回空或错误
    """
    print("[查询交易记录] 新接口暂不支持交易查询")
    return False, None, "新接口暂不支持交易查询"

