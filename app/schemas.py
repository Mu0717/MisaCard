"""
Pydantic 数据验证模型
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime
import json


class CardBase(BaseModel):
    """卡片基础模型"""
    card_id: str = Field(..., description="卡密")
    card_nickname: Optional[str] = Field(None, description="卡片昵称")
    card_header: Optional[str] = Field(None, description="备注卡头")
    card_limit: float = Field(default=0.0, description="额度")
    validity_hours: Optional[int] = Field(None, description="有效期（小时）")


class CardCreate(CardBase):
    """创建卡片请求模型"""
    pass


class CardUpdate(BaseModel):
    """更新卡片请求模型"""
    card_nickname: Optional[str] = None
    card_header: Optional[str] = None
    card_limit: Optional[float] = None
    validity_hours: Optional[int] = None
    status: Optional[str] = None


class CardResponse(CardBase):
    """卡片响应模型"""
    id: int
    card_number: Optional[str] = None
    card_cvc: Optional[str] = None
    card_exp_date: Optional[str] = None
    billing_address: Optional[str] = None
    status: str
    is_activated: bool
    create_time: datetime
    card_activation_time: Optional[datetime] = None
    exp_date: Optional[datetime] = None
    delete_date: Optional[datetime] = None
    refund_requested: bool = False
    refund_requested_time: Optional[datetime] = None
    is_used: bool = False
    used_time: Optional[datetime] = None
    is_sold: bool = False
    sold_time: Optional[datetime] = None
    is_external: bool = False
    card_header: Optional[str] = None
    legal_address: Optional[dict] = None

    @field_validator("legal_address", mode="before")
    @classmethod
    def parse_legal_address(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except:
                return None
        return v

    class Config:
        from_attributes = True


class CardImportItem(BaseModel):
    """txt导入单条数据模型"""
    card_id: str
    card_limit: float
    validity_hours: int
    card_header: Optional[str] = None


class CardImportRequest(BaseModel):
    """批量导入请求模型"""
    cards: list[CardImportItem]


class CardImportResponse(BaseModel):
    """批量导入响应模型"""
    success_count: int
    failed_count: int
    failed_items: list[dict]
    message: str


class ActivationRequest(BaseModel):
    """激活请求模型"""
    card_id: str


class BatchActivateRequest(BaseModel):
    """批量激活请求模型"""
    card_ids: list[str] = Field(..., description="卡密列表")
    concurrency: int = Field(default=5, ge=1, le=20, description="并发数（1-20）")
    max_retries: int = Field(default=3, ge=0, le=10, description="最大重试次数（0-10）")


class ActivationResponse(BaseModel):
    """激活响应模型"""
    success: bool
    message: str
    card_data: Optional[CardResponse] = None


class APIResponse(BaseModel):
    """通用API响应模型"""
    success: bool
    message: str
    data: Optional[dict] = None


class CardListResponse(BaseModel):
    """卡片列表响应模型（带分页信息）"""
    items: list[CardResponse]
    total: int
    skip: int
    limit: int


class CardStatusQueryRequest(BaseModel):
    """后台卡密状态查询请求。"""
    card_id: str = Field(..., min_length=1, max_length=512, description="完整卡密")

    @field_validator("card_id", mode="before")
    @classmethod
    def normalize_card_id(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value


class CardStatusBatchQueryRequest(BaseModel):
    """后台批量卡密状态查询请求。"""
    card_ids: list[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="卡密列表，最多 100 个",
    )
    concurrency: int = Field(default=5, ge=1, le=10, description="并发查询数")

    @field_validator("card_ids", mode="before")
    @classmethod
    def normalize_card_ids(cls, value):
        if not isinstance(value, list):
            return value

        normalized = []
        seen = set()
        for item in value:
            if not isinstance(item, str):
                raise ValueError("卡密必须是字符串")
            card_id = item.strip()
            if not card_id:
                continue
            if len(card_id) > 512:
                raise ValueError("单个卡密长度不能超过 512 个字符")
            if card_id not in seen:
                seen.add(card_id)
                normalized.append(card_id)

        if not normalized:
            raise ValueError("卡密列表不能为空")
        return normalized


class CardStatusData(BaseModel):
    """卡密状态摘要，不包含卡号、CVC 等敏感卡片信息。"""
    card_id: str
    provider: Optional[str] = None
    provider_label: Optional[str] = None
    query_source: str = "local"
    remote_status: Optional[str] = None
    remote_message: Optional[str] = None
    local_exists: bool = False
    card_nickname: Optional[str] = None
    card_header: Optional[str] = None
    card_limit: float = 0.0
    validity_hours: Optional[int] = None
    status: str
    is_activated: Optional[bool] = None
    is_used: Optional[bool] = None
    is_sold: Optional[bool] = None
    refund_requested: Optional[bool] = None
    is_external: Optional[bool] = None
    create_time: Optional[datetime] = None
    card_activation_time: Optional[datetime] = None
    exp_date: Optional[datetime] = None
    delete_date: Optional[datetime] = None
    used_time: Optional[datetime] = None
    sold_time: Optional[datetime] = None
    refund_requested_time: Optional[datetime] = None

    class Config:
        from_attributes = True


class CardStatusQueryResponse(BaseModel):
    """后台卡密状态查询响应。"""
    success: bool
    message: str
    data: CardStatusData


class CardStatusBatchItem(BaseModel):
    """批量状态查询的单条结果。"""
    card_id: str
    success: bool
    message: str
    data: Optional[CardStatusData] = None


class CardStatusBatchQueryResponse(BaseModel):
    """后台批量卡密状态查询响应。"""
    success: bool
    message: str
    total: int
    success_count: int
    failed_count: int
    items: list[CardStatusBatchItem]


class VocardVerifyRequest(BaseModel):
    """Vocard 验证码查询请求"""
    lastFour: str = Field(..., description="卡号后四位")


