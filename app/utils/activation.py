"""
卡片自动激活功能
保留原有 Next.js 项目的激活逻辑
"""
import httpx
from typing import Optional, Dict, Tuple
import json
import asyncio

from ..config import (
    MISACARD_API_BASE_URL, 
    MISACARD_API_HEADERS,
    ACTIVATION_MAX_RETRIES,
    ACTIVATION_RETRY_DELAY
)


# API 配置（从配置文件导入）
API_BASE_URL = MISACARD_API_BASE_URL
API_HEADERS = MISACARD_API_HEADERS

# 消费记录查询API基础URL
CARD_INFO_API_BASE_URL = "https://api.misacard.com/api/m/get_card_info"


async def query_card_from_api(card_id: str) -> Tuple[bool, Optional[Dict], Optional[str]]:
    """
    从 MisaCard API 查询卡片信息

    Args:
        card_id: 卡密

    Returns:
        (成功标志, 卡片数据, 错误信息)
    """
    try:
        timeout = httpx.Timeout(30.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, verify=False) as client:
            request_url = f"{API_BASE_URL}/{card_id}"
            print(f"\n{'='*60}")
            print(f"[查询卡片] 请求URL: {request_url}")
            print(f"[查询卡片] 请求Headers: {json.dumps(API_HEADERS, ensure_ascii=False, indent=2)}")
            
            response = await client.get(
                request_url,
                headers=API_HEADERS
            )

            print(f"[查询卡片] 响应状态码: {response.status_code}")
            print(f"[查询卡片] 响应内容: {response.text}")

            if response.status_code == 200:
                data = response.json()
                result = data.get("result")
                
                if result:
                    status = result.get("status", "未知")
                    print(f"[查询卡片] 卡片状态: {status}")
                    print(f"{'='*60}\n")
                    return True, result, None
                else:
                    print(f"[查询卡片] ✗ 查询失败: result为空")
                    print(f"{'='*60}\n")
                    return False, None, data.get("msg") or "卡片不存在"
            else:
                print(f"[查询卡片] ✗ 查询失败: HTTP状态码 {response.status_code}")
                print(f"{'='*60}\n")
                return False, None, f"API 请求失败: {response.status_code}"

    except httpx.TimeoutException as e:
        print(f"[查询卡片] 请求超时: {str(e)}")
        return False, None, f"请求超时: {str(e)}"
    except httpx.HTTPError as e:
        print(f"[查询卡片] HTTP错误: {str(e)}")
        return False, None, f"HTTP错误: {str(e)}"
    except Exception as e:
        print(f"[查询卡片] 异常: {str(e)}")
        return False, None, f"查询失败: {str(e)}"


async def activate_card_via_api(card_id: str, max_retries: int = None, retry_delay: int = None) -> Tuple[bool, Optional[Dict], Optional[str]]:
    """
    通过 MisaCard API 激活卡片（带自动轮询重试）

    Args:
        card_id: 卡密
        max_retries: 最大重试次数（默认从配置读取，默认20次）
        retry_delay: 重试间隔秒数（默认从配置读取，默认3秒）

    Returns:
        (成功标志, 激活后的卡片数据, 错误信息)
    """
    # 使用配置文件中的默认值
    if max_retries is None:
        max_retries = ACTIVATION_MAX_RETRIES
    if retry_delay is None:
        retry_delay = ACTIVATION_RETRY_DELAY
    
    retry_count = 0
    
    while retry_count <= max_retries:
        try:
            retry_text = f" (第 {retry_count + 1}/{max_retries + 1} 次尝试)" if retry_count > 0 else ""
            timeout = httpx.Timeout(30.0, connect=10.0)
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, verify=False) as client:
                request_url = f"{API_BASE_URL}/activate/{card_id}"
                print(f"\n{'='*60}")
                print(f"[激活卡片{retry_text}] 请求URL: {request_url}")
                print(f"[激活卡片] 请求方法: POST")
                print(f"[激活卡片] 请求Headers: {json.dumps(API_HEADERS, ensure_ascii=False, indent=2)}")
                
                response = await client.post(
                    request_url,
                    headers=API_HEADERS
                )
                
                print(f"[激活卡片] 响应状态码: {response.status_code}")
                print(f"[激活卡片] 响应内容: {response.text}")
                
                if response.status_code == 200:
                    data = response.json()
                    result = data.get("result")
                    error = data.get("error")
                    
                    # 检查是否有永久性错误（不应重试的情况）
                    if error and any(keyword in str(error) for keyword in ["已删除", "不存在", "已过期"]):
                        print(f"[激活卡片] ✗ 永久性错误，停止重试: {error}")
                        print(f"{'='*60}\n")
                        return False, None, str(error)
                    
                    if result:
                        status = result.get("status")
                        print(f"[激活卡片] 卡片状态: {status}")
                        
                        if status == "已激活":
                            print(f"[激活卡片] ✓ 激活成功!")
                            print(f"{'='*60}\n")
                            return True, result, None
                        else:
                            print(f"[激活卡片] ⚠️  状态不是'已激活'，当前状态: {status}")
                            # 状态不对也可能需要重试
                            if retry_count < max_retries:
                                print(f"[激活卡片] 将在 {retry_delay} 秒后重试...")
                                print(f"{'='*60}\n")
                                await asyncio.sleep(retry_delay)
                                retry_count += 1
                                continue
                            else:
                                print(f"[激活卡片] ✗ 已达到最大重试次数，激活失败")
                                print(f"{'='*60}\n")
                                return False, result, f"激活失败: 卡片状态为 {status}"
                    else:
                        # result为空，需要重试
                        print(f"[激活卡片] ⚠️  result为空（可能正在处理中）")
                        
                        if retry_count < max_retries:
                            print(f"[激活卡片] 将在 {retry_delay} 秒后重试...")
                            print(f"{'='*60}\n")
                            await asyncio.sleep(retry_delay)
                            retry_count += 1
                            continue
                        else:
                            print(f"[激活卡片] ✗ 已达到最大重试次数，激活失败")
                            print(f"{'='*60}\n")
                            return False, None, data.get("msg") or "激活失败: result为空"
                else:
                    print(f"[激活卡片] ✗ HTTP状态码异常: {response.status_code}")
                    
                    if retry_count < max_retries:
                        print(f"[激活卡片] 将在 {retry_delay} 秒后重试...")
                        print(f"{'='*60}\n")
                        await asyncio.sleep(retry_delay)
                        retry_count += 1
                        continue
                    else:
                        print(f"[激活卡片] ✗ 已达到最大重试次数")
                        print(f"{'='*60}\n")
                        return False, None, f"激活请求失败: {response.status_code}"

        except httpx.TimeoutException as e:
            print(f"[激活卡片] 请求超时: {str(e)}")
            if retry_count < max_retries:
                print(f"[激活卡片] 将在 {retry_delay} 秒后重试...")
                await asyncio.sleep(retry_delay)
                retry_count += 1
                continue
            else:
                return False, None, f"激活超时: {str(e)}"
                
        except httpx.HTTPError as e:
            print(f"[激活卡片] HTTP错误: {str(e)}")
            if retry_count < max_retries:
                print(f"[激活卡片] 将在 {retry_delay} 秒后重试...")
                await asyncio.sleep(retry_delay)
                retry_count += 1
                continue
            else:
                return False, None, f"HTTP错误: {str(e)}"
                
        except Exception as e:
            print(f"[激活卡片] 异常: {str(e)}")
            if retry_count < max_retries:
                print(f"[激活卡片] 将在 {retry_delay} 秒后重试...")
                await asyncio.sleep(retry_delay)
                retry_count += 1
                continue
            else:
                return False, None, f"激活失败: {str(e)}"
    
    # 理论上不会到这里，但保险起见
    return False, None, "激活失败: 已达到最大重试次数"


def is_card_activated(card_data: Dict) -> bool:
    """
    检查卡片是否已激活（新的准确判断逻辑）
    
    激活成功的标准：
    1. card_data 不为空
    2. status == "已激活"

    Args:
        card_data: 卡片数据字典

    Returns:
        True 如果已激活，否则 False
    """
    if not card_data:
        return False
    
    status = card_data.get("status")
    return status == "已激活"


def is_card_unactivated(card_data: Dict) -> bool:
    """
    检查卡片是否未激活（兼容旧逻辑）

    Args:
        card_data: 卡片数据字典

    Returns:
        True 如果未激活，否则 False
    """
    # 新的判断逻辑：status 不等于 "已激活"
    return not is_card_activated(card_data)


async def auto_activate_if_needed(card_id: str) -> Tuple[bool, Optional[Dict], str]:
    """
    自动激活流程（保留原有逻辑）
    1. 查询卡片信息
    2. 如果未激活，自动调用激活 API
    3. 返回最终的卡片数据

    Args:
        card_id: 卡密

    Returns:
        (成功标志, 卡片数据, 消息)
    """
    print(f"\n{'*'*60}")
    print(f"[自动激活流程] 开始处理卡密: {card_id}")
    print(f"{'*'*60}")
    
    # 步骤1: 查询卡片
    print(f"[自动激活流程] 步骤1: 查询卡片信息...")
    success, card_data, error = await query_card_from_api(card_id)
    if not success:
        print(f"[自动激活流程] 查询失败: {error}")
        return False, None, error or "查询失败"

    # 步骤2: 检查是否需要激活
    print(f"[自动激活流程] 步骤2: 检查激活状态...")
    current_status = card_data.get("status", "未知")
    is_activated = is_card_activated(card_data)
    print(f"[自动激活流程] 当前状态: {current_status}, 是否已激活: {is_activated}")
    
    if not is_activated:
        # 需要激活
        print(f"[自动激活流程] 步骤3: 执行自动激活...")
        success, activated_data, error = await activate_card_via_api(card_id)
        
        if success:
            # 再次验证激活后的状态
            activated_status = activated_data.get("status") if activated_data else None
            final_is_activated = is_card_activated(activated_data)
            
            print(f"[自动激活流程] 激活后状态: {activated_status}, 是否已激活: {final_is_activated}")
            
            if final_is_activated:
                print(f"[自动激活流程] ✓ 激活成功! 状态已确认为'已激活'")
                print(f"{'*'*60}\n")
                return True, activated_data, "卡片已自动激活"
            else:
                print(f"[自动激活流程] ⚠️  API调用成功，但卡片状态不是'已激活'")
                print(f"{'*'*60}\n")
                return False, activated_data, f"激活未完成: 卡片状态为 {activated_status}"
        else:
            # 激活API调用失败
            print(f"[自动激活流程] ✗ 激活失败: {error}")
            print(f"{'*'*60}\n")
            return False, card_data, f"激活失败: {error}"

    # 步骤3: 已激活，直接返回
    print(f"[自动激活流程] ✓ 卡片状态已是'已激活'，无需处理")
    print(f"{'*'*60}\n")
    return True, card_data, "卡片已激活"


def extract_card_info(api_response: Dict) -> Dict:
    """
    从 API 响应中提取卡片信息

    Args:
        api_response: API 返回的卡片数据

    Returns:
        格式化的卡片信息字典
    """
    return {
        "card_number": api_response.get("card_number"),
        "card_cvc": api_response.get("card_cvc"),
        "card_exp_date": api_response.get("card_exp_date"),  # 信用卡有效期格式（MM/YY）
        "billing_address": api_response.get("billing_address"),
        "card_nickname": api_response.get("card_nickname"),
        "card_limit": api_response.get("card_limit", 0),
        "status": api_response.get("status", "unknown"),
        "create_time": api_response.get("create_time"),
        "card_activation_time": api_response.get("card_activation_time"),
        "validity_hours": api_response.get("exp_date"),  # API的exp_date是有效期小时数
        "exp_date": api_response.get("delete_date"),  # API的delete_date才是系统过期时间
    }


async def get_card_transactions(card_number: str) -> Tuple[bool, Optional[Dict], Optional[str]]:
    """
    从 MisaCard API 查询卡片消费记录

    Args:
        card_number: 卡号

    Returns:
        (成功标志, 卡片信息和交易数据, 错误信息)
    """
    try:
        # 增加超时时间到30秒，禁用SSL验证
        timeout = httpx.Timeout(30.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, verify=False) as client:
            request_url = f"{CARD_INFO_API_BASE_URL}/{card_number}"
            print(f"\n{'='*60}")
            print(f"[查询交易记录] 请求URL: {request_url}")
            print(f"[查询交易记录] 请求Headers: {json.dumps(API_HEADERS, ensure_ascii=False, indent=2)}")
            
            response = await client.get(
                request_url,
                headers=API_HEADERS
            )

            print(f"[查询交易记录] 响应状态码: {response.status_code}")
            print(f"[查询交易记录] 响应内容: {response.text}")

            if response.status_code == 200:
                data = response.json()
                result = data.get("result")
                
                if result:
                    print(f"[查询交易记录] ✓ 查询成功")
                    print(f"{'='*60}\n")
                    return True, result, None
                else:
                    print(f"[查询交易记录] ✗ 查询失败: result为空")
                    print(f"{'='*60}\n")
                    return False, None, data.get("msg") or "无法获取卡片信息"
            else:
                print(f"[查询交易记录] ✗ 查询失败: HTTP状态码 {response.status_code}")
                print(f"{'='*60}\n")
                return False, None, f"API 请求失败: {response.status_code}"

    except httpx.TimeoutException as e:
        print(f"[查询交易记录] 请求超时: {str(e)}")
        return False, None, f"请求超时: {str(e)}"
    except httpx.HTTPError as e:
        print(f"[查询交易记录] HTTP错误: {str(e)}")
        return False, None, f"HTTP错误: {str(e)}"
    except Exception as e:
        print(f"[查询交易记录] 异常: {str(e)}")
        return False, None, f"查询失败: {str(e)}"
