
from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., description="用户输入")
    thread_id: str = Field(default="default", description="会话 ID")
    user_id: str = Field(default="anonymous")


class ChatResponse(BaseModel):
    thread_id: str
    answer: str
    intent: Optional[str] = None
    confidence: float = 0.0
    citations: List[Dict[str, Any]] = []
    flow_status: str = "succeeded"
    hitl_pending: bool = False
    hitl_reason: Optional[str] = None


class TicketCreateRequest(BaseModel):
    device_model: str
    error_code: str
    description: str = ""
    contact: str = ""
    address: str = ""
    ticket_type: str = "repair"  # repair / return / exchange / refund / complaint / inquiry


class TicketResponse(BaseModel):
    ticket_id: str
    status: str
    assigned_to: Optional[str] = None
    created_at: str


class KnowledgeIngestRequest(BaseModel):
    doc_id: str
    source: str = ""
    content: str


class HealthResponse(BaseModel):
    status: str
    version: str = "0.1.0"


# ============ 工程师 ============
class EngineerCreate(BaseModel):
    name: str
    skills: List[str] = []
    region: str = ""
    phone: str = ""
    feishu_open_id: str = ""
    status: str = "online"
    max_load: int = 10


class EngineerUpdate(BaseModel):
    name: Optional[str] = None
    skills: Optional[List[str]] = None
    region: Optional[str] = None
    phone: Optional[str] = None
    feishu_open_id: Optional[str] = None
    status: Optional[str] = None
    max_load: Optional[int] = None


class EngineerResponse(BaseModel):
    id: int
    name: str
    skills: List[str] = []
    region: str = ""
    phone: str = ""
    feishu_open_id: str = ""
    status: str
    current_load: int
    max_load: int
    created_at: Optional[str] = None


class TicketUpdateRequest(BaseModel):
    """补全或修改工单字段。只传需要改的字段。"""
    device_model: Optional[str] = None
    error_code: Optional[str] = None
    description: Optional[str] = None
    contact: Optional[str] = None
    address: Optional[str] = None


# ============ 客户 ============
class CustomerCreate(BaseModel):
    name: str
    phone: str
    email: str = ""
    address: str = ""
    vip_level: str = "normal"


class CustomerResponse(BaseModel):
    customer_id: str
    name: str
    phone: str
    vip_level: str
    risk_level: str
    risk_score: int
    total_orders: int
    total_refunds: int
    total_complaints: int
    total_tickets: int
    created_at: Optional[str] = None


# ============ 退款 ============
class RefundCreateRequest(BaseModel):
    ticket_id: str = ""
    customer_id: str
    order_id: str
    refund_type: str = "refund_only"
    amount: float
    reason: str = ""


class RefundApprovalRequest(BaseModel):
    decision: str  # approve / reject
    note: str = ""


class RefundResponse(BaseModel):
    refund_id: str
    ticket_id: str
    customer_id: str
    order_id: str
    refund_type: str
    amount: float
    status: str
    ai_suggestion: str
    ai_confidence: float
    ai_reason: str
    risk_flag: str
    approver: Optional[str] = None
    approval_note: Optional[str] = None
    created_at: Optional[str] = None
