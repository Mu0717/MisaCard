"""
卡片 CRUD API 端点
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import asyncio

from .. import crud, schemas, models
from ..database import get_db
from ..utils.activation import auto_activate_if_needed, extract_card_info, query_card_from_api, get_card_transactions, is_card_activated
from ..utils.auth import get_current_user

router = APIRouter(prefix="/cards", tags=["cards"])


@router.post("/", response_model=schemas.CardResponse, status_code=201)
async def create_card(
    card: schemas.CardCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """创建新卡片（需要鉴权）"""
    # 检查卡密是否已存在
    existing_card = crud.get_card_by_id(db, card.card_id)
    if existing_card:
        raise HTTPException(status_code=400, detail="卡密已存在")

    db_card = crud.create_card(db, card)
    return db_card


@router.get("/", response_model=List[schemas.CardResponse])
async def list_cards(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=50000),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """获取卡片列表（支持分页、筛选、搜索）（需要鉴权）"""
    cards = crud.get_cards(db, skip=skip, limit=limit, status=status, search=search)
    return cards


@router.get("/{card_id}", response_model=schemas.CardResponse)
async def get_card(
    card_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """获取单个卡片信息（需要鉴权）"""
    db_card = crud.get_card_by_id(db, card_id)
    if not db_card:
        raise HTTPException(status_code=404, detail="卡片不存在")
    return db_card


@router.put("/{card_id}", response_model=schemas.CardResponse)
async def update_card(
    card_id: str,
    card_update: schemas.CardUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """更新卡片信息（需要鉴权）"""
    db_card = crud.update_card(db, card_id, card_update)
    if not db_card:
        raise HTTPException(status_code=404, detail="卡片不存在")
    return db_card


@router.delete("/{card_id}", response_model=schemas.APIResponse)
async def delete_card(
    card_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """删除卡片（软删除）（需要鉴权）"""
    success = crud.delete_card(db, card_id)
    if not success:
        raise HTTPException(status_code=404, detail="卡片不存在")
    return {"success": True, "message": "卡片已删除"}


@router.post("/batch/activate", response_model=schemas.APIResponse)
async def batch_activate_cards(
    card_ids: schemas.BatchActivateRequest,
    db: Session = Depends(get_db)
):
    """
    批量激活卡片（并发处理）
    支持同时激活多张卡片，自动重试失败的卡片
    """
    if not card_ids.card_ids:
        raise HTTPException(status_code=400, detail="卡片ID列表不能为空")
    
    print(f"\n{'#'*60}")
    print(f"[批量激活] 开始批量激活 {len(card_ids.card_ids)} 张卡片")
    print(f"[批量激活] 并发数: {card_ids.concurrency}")
    print(f"[批量激活] 最大重试次数: {card_ids.max_retries}")
    print(f"{'#'*60}\n")
    
    # 创建信号量来限制并发数
    semaphore = asyncio.Semaphore(card_ids.concurrency)
    
    # 存储激活结果
    results = {
        "success": [],
        "failed": [],
        "total": len(card_ids.card_ids),
        "success_count": 0,
        "failed_count": 0
    }
    
    async def activate_single_card(card_id: str, retry_count: int = 0):
        """激活单张卡片（带重试逻辑）"""
        async with semaphore:  # 限制并发数
            retry_text = f" (重试 {retry_count}/{card_ids.max_retries})" if retry_count > 0 else ""
            print(f"[批量激活] 正在处理: {card_id}{retry_text}")
            
            try:
                # 检查本地数据库是否已有该卡且已激活
                db_card = crud.get_card_by_id(db, card_id)
                if db_card and db_card.is_activated:
                    print(f"[批量激活] ✓ 本地已激活，跳过API请求: {card_id}")
                    result = {
                        "card_id": card_id,
                        "success": True,
                        "message": "卡片已激活 (从本地读取)",
                        "retry_count": retry_count,
                        "status": "已激活"
                    }
                    results["success"].append(result)
                    results["success_count"] += 1
                    return result

                # 自动激活流程
                success, card_data, message = await auto_activate_if_needed(card_id)
                
                if not success:
                    # 激活失败
                    # 尝试记录日志（如果卡片存在）
                    db_card = crud.get_card_by_id(db, card_id)
                    if db_card:
                        crud.create_activation_log(db, card_id, "failed", error_message=message)
                    
                    # 检查是否需要重试
                    if retry_count < card_ids.max_retries:
                        print(f"[批量激活] ⚠️  失败，将重试: {card_id}")
                        await asyncio.sleep(1)  # 延迟后重试
                        return await activate_single_card(card_id, retry_count + 1)
                    else:
                        result = {
                            "card_id": card_id,
                            "success": False,
                            "message": message,
                            "retry_count": retry_count
                        }
                        results["failed"].append(result)
                        results["failed_count"] += 1
                        print(f"[批量激活] ✗ 最终失败: {card_id} - {message}")
                        return result
                
                # 验证卡片是否真正激活（status == "已激活"/或者有数据）
                if not is_card_activated(card_data):
                    status = card_data.get("status") if card_data else "未知"
                    error_msg = f"激活未完成: 卡片状态为 {status}"
                    
                    db_card = crud.get_card_by_id(db, card_id)
                    if db_card:
                        crud.create_activation_log(db, card_id, "failed", error_message=error_msg)
                    
                    # 检查是否需要重试
                    if retry_count < card_ids.max_retries:
                        print(f"[批量激活] ⚠️  状态异常，将重试: {card_id} - {error_msg}")
                        await asyncio.sleep(1)
                        return await activate_single_card(card_id, retry_count + 1)
                    else:
                        result = {
                            "card_id": card_id,
                            "success": False,
                            "message": error_msg,
                            "retry_count": retry_count
                        }
                        results["failed"].append(result)
                        results["failed_count"] += 1
                        print(f"[批量激活] ✗ 最终失败: {card_id} - {error_msg}")
                        return result
                
                # 提取卡片信息并验证
                card_info = extract_card_info(card_data)
                
                # 如果没有卡号但激活成功，尽量接受（取决于业务需求，这里先暂时要求必须有卡号）
                if not card_info.get("card_number"):
                    # 尝试宽容处理，如果没有卡号，可能是还在处理中?
                    # 但为了保证一致性，如果真的“已激活”应该有卡号。
                    pass
                
                # 更新或创建数据库记录
                from datetime import datetime
                exp_date = None
                if card_info.get("exp_date"):
                    try:
                        exp_date = datetime.fromisoformat(card_info["exp_date"].replace('Z', '+00:00'))
                    except:
                        pass
                
                # 尝试更新，如果返回None说明卡片不存在，需要创建
                db_card = crud.activate_card_in_db(
                    db,
                    card_id,
                    str(card_info.get("card_number") or ""),
                    str(card_info.get("card_cvc") or ""),
                    str(card_info.get("card_exp_date") or ""),
                    card_info.get("billing_address"),
                    validity_hours=card_info.get("validity_hours"),
                    exp_date=exp_date
                )
                
                if not db_card:
                    # 卡片不存在，自动创建
                    print(f"[批量激活] ⚠️  本地库无此卡，正在自动创建: {card_id}")
                    new_card = schemas.CardCreate(
                        card_id=card_id,
                        card_limit=float(card_info.get("card_limit") or 0.0),
                        card_nickname=f"Auto-Import {card_info.get('card_limit') or ''}",
                        validity_hours=card_info.get("validity_hours")
                    )
                    crud.create_card(db, new_card, is_external=True)
                    # 再次尝试更新激活信息
                    crud.activate_card_in_db(
                        db,
                        card_id,
                        str(card_info.get("card_number") or ""),
                        str(card_info.get("card_cvc") or ""),
                        str(card_info.get("card_exp_date") or ""),
                        card_info.get("billing_address"),
                        validity_hours=card_info.get("validity_hours"),
                        exp_date=exp_date
                    )
                
                try:
                    crud.create_activation_log(db, card_id, "success")
                except Exception:
                    # 忽略日志创建失败（例如并发导致的主键冲突等，虽然不太可能）
                    pass
                
                result = {
                    "card_id": card_id,
                    "success": True,
                    "message": message,
                    "retry_count": retry_count,
                    "status": "已激活"
                }
                results["success"].append(result)
                results["success_count"] += 1
                print(f"[批量激活] ✓ 成功: {card_id} (状态: 已激活)")
                return result
                
            except Exception as e:
                error_msg = f"处理异常: {str(e)}"
                
                # 检查是否需要重试
                if retry_count < card_ids.max_retries:
                    print(f"[批量激活] ⚠️  异常，将重试: {card_id} - {error_msg}")
                    await asyncio.sleep(1)
                    return await activate_single_card(card_id, retry_count + 1)
                else:
                    result = {
                        "card_id": card_id,
                        "success": False,
                        "message": error_msg,
                        "retry_count": retry_count
                    }
                    results["failed"].append(result)
                    results["failed_count"] += 1
                    print(f"[批量激活] ✗ 最终失败: {card_id} - {error_msg}")
                    return result
    
    # 并发执行所有激活任务
    tasks = [activate_single_card(card_id) for card_id in card_ids.card_ids]
    await asyncio.gather(*tasks)
    
    print(f"\n{'#'*60}")
    print(f"[批量激活] 批量激活完成!")
    print(f"[批量激活] 总数: {results['total']}")
    print(f"[批量激活] 成功: {results['success_count']}")
    print(f"[批量激活] 失败: {results['failed_count']}")
    print(f"{'#'*60}\n")
    
    return {
        "success": True,
        "message": f"批量激活完成: 成功 {results['success_count']}/{results['total']}",
        "data": results
    }


@router.post("/{card_id}/activate", response_model=schemas.ActivationResponse)
async def activate_card(
    card_id: str,
    db: Session = Depends(get_db)
):
    """
    激活卡片（保留原有自动激活逻辑）
    1. 调用 MisaCard API 查询和激活
    2. 更新本地数据库（如果不存在则自动创建）
    3. 记录激活日志
    """
    # 检查本地是否已激活
    db_card = crud.get_card_by_id(db, card_id)
    if db_card and db_card.is_activated:
        print(f"[激活卡片] ✓ 本地已激活，直接返回: {card_id}")
        return {
            "success": True,
            "message": "卡片已激活",
            "card_data": db_card
        }

    # 直接进行自动激活流程，不预检数据库
    success, card_data, message = await auto_activate_if_needed(card_id)

    if not success:
        # 尝试记录失败日志（如果卡片存在）
        db_card = crud.get_card_by_id(db, card_id)
        if db_card:
            crud.create_activation_log(db, card_id, "failed", error_message=message)
        raise HTTPException(status_code=400, detail=message)

    # 验证卡片是否真正激活
    if not is_card_activated(card_data):
        status = card_data.get("status") if card_data else "未知"
        error_msg = f"激活未完成: 卡片状态为 {status}"
        
        db_card = crud.get_card_by_id(db, card_id)
        if db_card:
            crud.create_activation_log(db, card_id, "failed", error_message=error_msg)
            
        raise HTTPException(status_code=400, detail=error_msg)

    # 提取卡片信息
    card_info = extract_card_info(card_data)

    # 验证卡号等关键信息是否存在 (允许某些情况下为空，但警告)
    if not card_info.get("card_number"):
        # 这里可以选择报错或者继续。如果"已激活"但没卡号，可能是还没生成完全。
        # 暂时保持严格检查，或者视具体响应而定
        pass
        # error_msg = "激活状态异常: 状态为'已激活'但缺少卡号信息"
        # raise HTTPException(status_code=400, detail=error_msg)

    # 更新数据库中的卡片信息
    from datetime import datetime
    exp_date = None
    if card_info.get("exp_date"):
        try:
            exp_date = datetime.fromisoformat(card_info["exp_date"].replace('Z', '+00:00'))
        except:
            pass

    # 尝试更新
    db_card = crud.activate_card_in_db(
        db,
        card_id,
        str(card_info.get("card_number") or ""),
        str(card_info.get("card_cvc") or ""),
        str(card_info.get("card_exp_date") or ""),
        card_info.get("billing_address"),
        validity_hours=card_info.get("validity_hours"),
        exp_date=exp_date
    )

    if not db_card:
         # 卡片不存在，自动创建
        print(f"[激活卡片] ⚠️  本地库无此卡，正在自动创建: {card_id}")
        new_card = schemas.CardCreate(
            card_id=card_id,
            card_limit=float(card_info.get("card_limit") or 0.0),
            card_nickname=f"Auto-Active {card_info.get('card_limit') or ''}",
            validity_hours=card_info.get("validity_hours")
        )
        crud.create_card(db, new_card, is_external=True)
        
        # 再次更新激活信息
        db_card = crud.activate_card_in_db(
            db,
            card_id,
            str(card_info.get("card_number") or ""),
            str(card_info.get("card_cvc") or ""),
            str(card_info.get("card_exp_date") or ""),
            card_info.get("billing_address"),
            validity_hours=card_info.get("validity_hours"),
            exp_date=exp_date
        )

    # 记录成功日志
    if db_card:
        try:
            crud.create_activation_log(db, card_id, "success")
        except:
            pass

    # 重新获取更新后的卡片
    db_card = crud.get_card_by_id(db, card_id)
    return {
        "success": True,
        "message": message,
        "card_data": db_card
    }


@router.post("/{card_id}/query", response_model=schemas.ActivationResponse)
async def query_card(
    card_id: str,
    db: Session = Depends(get_db)
):
    """
    从API查询卡片信息并更新数据库
    用于获取最新的卡片状态、过期时间等信息
    """
    # 检查卡片是否存在
    db_card = crud.get_card_by_id(db, card_id)
    if not db_card:
        raise HTTPException(status_code=404, detail="卡片不存在于本地数据库")

    # 从API查询卡片信息
    success, card_data, error = await query_card_from_api(card_id)

    if not success:
        raise HTTPException(status_code=400, detail=error or "查询失败")

    # 提取卡片信息
    card_info = extract_card_info(card_data)

    # 解析过期时间（API返回的delete_date字段，是UTC+8时间）
    from datetime import datetime, timezone, timedelta
    exp_date = None
    if card_info.get("exp_date"):
        try:
            # 解析时间字符串
            dt = datetime.fromisoformat(card_info["exp_date"].replace('Z', '+00:00'))

            # 如果是 naive datetime（没有时区信息），说明是 UTC+8 时间
            if dt.tzinfo is None:
                # 先标记为 UTC+8
                utc8 = timezone(timedelta(hours=8))
                dt = dt.replace(tzinfo=utc8)
                # 转换为 UTC 时间
                exp_date = dt.astimezone(timezone.utc)
            else:
                # 如果已经有时区信息，转换为 UTC
                exp_date = dt.astimezone(timezone.utc)
        except:
            pass

    # 更新数据库中的卡片信息
    update_data = schemas.CardUpdate(
        card_limit=card_info.get("card_limit"),
        status=card_info.get("status")
    )

    # 如果有卡号信息，说明已激活，更新完整信息
    if card_info.get("card_number"):
        crud.activate_card_in_db(
            db,
            card_id,
            str(card_info["card_number"]),
            str(card_info["card_cvc"]),
            card_info["card_exp_date"],
            card_info.get("billing_address"),
            validity_hours=card_info.get("validity_hours"),
            exp_date=exp_date
        )
    else:
        # 未激活，只更新基本信息和过期时间
        db_card.validity_hours = card_info.get("validity_hours")
        db_card.exp_date = exp_date
        crud.update_card(db, card_id, update_data)

    # 重新获取更新后的卡片
    db_card = crud.get_card_by_id(db, card_id)
    return {
        "success": True,
        "message": "查询成功",
        "card_data": db_card
    }


@router.get("/{card_id}/logs", response_model=List[dict])
async def get_activation_logs(
    card_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """获取卡片的激活历史记录（需要鉴权）"""
    logs = crud.get_activation_logs(db, card_id)
    return [
        {
            "id": log.id,
            "status": log.status,
            "error_message": log.error_message,
            "activation_time": log.activation_time,
        }
        for log in logs
    ]


@router.post("/{card_id}/refund", response_model=schemas.APIResponse)
async def toggle_refund_status(
    card_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    切换卡片的退款状态（标记/取消标记退款）（需要鉴权）
    """
    from datetime import datetime

    db_card = crud.get_card_by_id(db, card_id)
    if not db_card:
        raise HTTPException(status_code=404, detail="卡片不存在")

    # 切换退款状态
    db_card.refund_requested = not db_card.refund_requested

    if db_card.refund_requested:
        from datetime import timezone
        db_card.refund_requested_time = datetime.now(timezone.utc)
        message = "已标记为申请退款"
    else:
        db_card.refund_requested_time = None
        message = "已取消退款标记"

    db.commit()
    db.refresh(db_card)

    return {
        "success": True,
        "message": message,
        "data": {"refund_requested": db_card.refund_requested}
    }


@router.post("/{card_id}/mark-used", response_model=schemas.APIResponse)
async def toggle_used_status(
    card_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    切换卡片的使用状态（标记/取消标记已使用）（需要鉴权）
    """
    from datetime import datetime, timezone

    db_card = crud.get_card_by_id(db, card_id)
    if not db_card:
        raise HTTPException(status_code=404, detail="卡片不存在")

    # 切换使用状态
    db_card.is_used = not db_card.is_used

    if db_card.is_used:
        db_card.used_time = datetime.now(timezone.utc)
        message = "已标记为已使用"
    else:
        db_card.used_time = None
        message = "已取消使用标记"

    db.commit()
    db.refresh(db_card)

    return {
        "success": True,
        "message": message,
        "data": {"is_used": db_card.is_used}
    }


@router.post("/{card_id}/mark-sold", response_model=schemas.APIResponse)
async def toggle_sold_status(
    card_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    切换卡片的售卖状态（标记/取消标记已售卖）（需要鉴权）
    """
    from datetime import datetime, timezone

    db_card = crud.get_card_by_id(db, card_id)
    if not db_card:
        raise HTTPException(status_code=404, detail="卡片不存在")

    # 切换售卖状态
    db_card.is_sold = not db_card.is_sold

    if db_card.is_sold:
        db_card.sold_time = datetime.now(timezone.utc)
        message = "已标记为已售卖"
    else:
        db_card.sold_time = None
        message = "已取消售卖标记"

    db.commit()
    db.refresh(db_card)

    return {
        "success": True,
        "message": message,
        "data": {"is_sold": db_card.is_sold}
    }


@router.get("/batch/unreturned-card-numbers", response_model=schemas.APIResponse)
async def get_unreturned_card_numbers(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    获取所有已过期、未退款且已激活的卡号列表（需要鉴权）
    用于批量复制和申请退款
    """
    # 先更新所有过期卡片的状态
    crud.update_expired_cards(db)

    # 筛选条件：已过期 + 已激活 + 未退款 + 有卡号
    cards = db.query(models.Card).filter(
        models.Card.status == 'expired',  # 只获取已过期的卡片
        models.Card.is_activated == True,
        models.Card.refund_requested == False,
        models.Card.card_number.isnot(None)
    ).all()

    card_numbers = [str(card.card_number) for card in cards]

    return {
        "success": True,
        "message": f"找到 {len(card_numbers)} 张已过期未退款的卡片",
        "data": {
            "count": len(card_numbers),
            "card_numbers": card_numbers
        }
    }


@router.get("/{card_id}/transactions", response_model=schemas.APIResponse)
async def get_card_transaction_history(
    card_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    获取卡片的消费记录（需要鉴权）
    需要卡片已激活（有卡号）才能查询
    """
    # 检查卡片是否存在
    db_card = crud.get_card_by_id(db, card_id)
    if not db_card:
        raise HTTPException(status_code=404, detail="卡片不存在")

    # 检查卡片是否已激活
    if not db_card.card_number:
        raise HTTPException(status_code=400, detail="卡片未激活，无法查询消费记录")

    # 从API查询消费记录
    success, card_info, error = await get_card_transactions(str(db_card.card_number))

    if not success:
        raise HTTPException(status_code=400, detail=error or "查询消费记录失败")

    return {
        "success": True,
        "message": "查询成功",
        "data": card_info
    }


@router.post("/{card_id}/transactions/query", response_model=schemas.APIResponse)
async def query_card_transactions_by_card_id(
    card_id: str,
    db: Session = Depends(get_db)
):
    """
    通过卡密查询交易记录（不需要鉴权，用于查询激活页面）
    需要卡片已激活（有卡号）才能查询
    """
    # 检查卡片是否存在
    db_card = crud.get_card_by_id(db, card_id)
    if not db_card:
        raise HTTPException(status_code=404, detail="卡片不存在")

    # 检查卡片是否已激活
    if not db_card.card_number:
        raise HTTPException(status_code=400, detail="卡片未激活，无法查询消费记录")

    # 从API查询消费记录
    success, card_info, error = await get_card_transactions(str(db_card.card_number))

    if not success:
        raise HTTPException(status_code=400, detail=error or "查询消费记录失败")

    return {
        "success": True,
        "message": "查询成功",
        "data": card_info
    }


@router.post("/query-by-card-number/{card_number}", response_model=schemas.APIResponse)
async def query_transactions_by_card_number(
    card_number: str
):
    """
    通过卡号查询交易记录（不需要鉴权，用于查询激活页面的卡号查询功能）
    """
    # 从API查询消费记录
    success, card_info, error = await get_card_transactions(card_number)

    if not success:
        raise HTTPException(status_code=400, detail=error or "查询消费记录失败")

    return {
        "success": True,
        "message": "查询成功",
        "data": card_info
    }


@router.get("/query/by-limit", response_model=schemas.APIResponse)
async def query_cards_by_limit(
    limit: float = Query(..., description="卡片额度"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    根据额度查询卡密信息（需要鉴权）
    返回所有匹配该额度的卡片信息
    """
    # 先更新所有过期卡片的状态
    crud.update_expired_cards(db)
    
    # 查询指定额度的卡片（排除已删除的）
    cards = db.query(models.Card).filter(
        models.Card.card_limit == limit,
        models.Card.status != 'deleted'
    ).all()
    
    if not cards:
        return {
            "success": False,
            "message": f"未找到额度为 ${limit} 的卡片",
            "data": {
                "count": 0,
                "cards": []
            }
        }
    
    # 构建返回数据
    card_list = []
    for card in cards:
        card_list.append({
            "card_id": card.card_id,
            "card_nickname": card.card_nickname,
            "card_limit": card.card_limit,
            "card_number": card.card_number,
            "card_cvc": card.card_cvc,
            "card_exp_date": card.card_exp_date,
            "status": card.status,
            "is_activated": card.is_activated,
            "is_used": card.is_used,
            "refund_requested": card.refund_requested,
            "create_time": card.create_time.isoformat() if card.create_time else None,
            "exp_date": card.exp_date.isoformat() if card.exp_date else None
        })
    
    return {
        "success": True,
        "message": f"找到 {len(cards)} 张额度为 ${limit} 的卡片",
        "data": {
            "count": len(cards),
            "limit": limit,
            "cards": card_list
        }
    }
