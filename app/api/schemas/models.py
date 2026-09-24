
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
