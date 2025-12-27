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
        print(f"[激活卡片] 开始调用 Mercury API Redeem: {card_id}")
        
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
        
    # 卡号 (pan)
    info["card_number"] = card_data.get("pan") or card_data.get("card_number")
    
    # CVV
    info["card_cvc"] = card_data.get("cvv") or card_data.get("card_cvc")
    
    # 有效期格式化 (MM/YY)
    exp_month = str(card_data.get("exp_month") or "")
    exp_year = str(card_data.get("exp_year") or "")
    
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
    # 强制统一账单地址
    info["billing_address"] = "41 Glenn Rd C23, East Hartford, CT 06118"
    info["card_nickname"] = card_data.get("card_nickname") or f"Card {info['card_number'][-4:] if info['card_number'] else ''}"
    info["card_limit"] = card_data.get("card_limit", 0)
    info["status"] = "已激活" if api_response.get("success") else "unknown"
    info["create_time"] = card_data.get("created_time")
    
    # 计算 validity_hours
    expire_minutes = api_response.get("expire_minutes")
    if expire_minutes is not None:
        info["validity_hours"] = int(expire_minutes) / 60
    else:
        info["validity_hours"] = card_data.get("validity_hours")
        
    # 计算系统过期时间 (这里视为激活时间 + expire_minutes)
    # 使用中国时区 (UTC+8)
    # 用户逻辑：卡密激活的时间(即现在) + expire_minutes
    
    calculated_exp_date = None
    if expire_minutes is not None:
        try:
            # 定义中国时区
            china_tz = timezone(timedelta(hours=8))
            
            # 使用当前时间作为激活时间
            dt = datetime.now(china_tz)
            
            # 加上过期分钟数
            exp_dt = dt + timedelta(minutes=int(expire_minutes))
            calculated_exp_date = exp_dt.isoformat()
        except Exception as e:
            print(f"计算过期时间出错: {e}")
            pass
            
    # 优先使用计算出的时间，否则回退到 API 返回的时间
    info["exp_date"] = calculated_exp_date or card_data.get("expire_time") or card_data.get("delete_date")
    
    return info


async def get_card_transactions(card_number: str) -> Tuple[bool, Optional[Dict], Optional[str]]:
    """
    查询交易记录
    目前 Mercury API 未提供明确的交易查询接口，暂时返回空或错误
    """
    print("[查询交易记录] 新接口暂不支持交易查询")
    return False, None, "新接口暂不支持交易查询"

