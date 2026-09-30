"""客户 + 订单 API。"""
from __future__ import annotations
import os
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.schemas.models import CustomerCreate, CustomerResponse
from app.db.models.customer import Customer
from app.db.models.order import Order
from app.db.models.ticket import Ticket
from app.db.models.refund import RefundRequest
from app.db.session import session_scope

router = APIRouter(prefix="/customers", tags=["customers"])


def _to_resp(c: Customer) -> CustomerResponse:
    return CustomerResponse(**c.to_dict())


@router.get("", response_model=list[CustomerResponse])
async def list_customers(
    vip_level: Optional[str] = None,
    risk_level: Optional[str] = None,
    keyword: Optional[str] = None,
):
    from sqlalchemy import or_
    with session_scope() as s:
        q = select(Customer).order_by(Customer.customer_id)
        if vip_level:
            q = q.where(Customer.vip_level == vip_level)
        if risk_level:
            q = q.where(Customer.risk_level == risk_level)
        if keyword:
            kw = f"%{keyword.strip()}%"
            q = q.where(or_(
                Customer.customer_id.like(kw),
                Customer.name.like(kw),
                Customer.phone.like(kw),
                Customer.email.like(kw),
                Customer.address.like(kw),
            ))
        rows = s.execute(q).scalars().all()
        return [_to_resp(c) for c in rows]


@router.post("", response_model=CustomerResponse)
async def create_customer(req: CustomerCreate):
    with session_scope() as s:
        exists = s.execute(select(Customer).where(Customer.phone == req.phone)).scalar_one_or_none()
        if exists:
            raise HTTPException(status_code=409, detail="手机号已存在")
        cid = f"C{uuid4().hex[:6].upper()}"
        c = Customer(
            customer_id=cid,
            name=req.name,
            phone=req.phone,
            email=req.email,
            address=req.address,
            vip_level=req.vip_level,
        )
        s.add(c)
        s.flush()
        return _to_resp(c)


@router.get("/{customer_id}")
async def get_customer(customer_id: str):
    with session_scope() as s:
        c = s.get(Customer, customer_id)
        if c is None:
            raise HTTPException(status_code=404, detail="客户不存在")
        return c.to_dict()


@router.get("/{customer_id}/orders")
async def get_customer_orders(customer_id: str):
    with session_scope() as s:
        rows = s.execute(
            select(Order).where(Order.customer_id == customer_id).order_by(Order.created_at.desc())
        ).scalars().all()
        return {"total": len(rows), "items": [o.to_dict() for o in rows]}


@router.get("/{customer_id}/tickets")
async def get_customer_tickets(customer_id: str):
    """客户工单：通过 contact 里含手机号匹配。"""
    with session_scope() as s:
        c = s.get(Customer, customer_id)
        if c is None:
            raise HTTPException(status_code=404, detail="客户不存在")
        rows = s.execute(
            select(Ticket).where(Ticket.contact.like(f"%{c.phone}%")).order_by(Ticket.created_at.desc())
        ).scalars().all()
        return {"total": len(rows), "items": [t.to_dict() for t in rows]}


@router.get("/{customer_id}/refunds")
async def get_customer_refunds(customer_id: str):
    with session_scope() as s:
        rows = s.execute(
            select(RefundRequest).where(RefundRequest.customer_id == customer_id).order_by(RefundRequest.created_at.desc())
        ).scalars().all()
        return {"total": len(rows), "items": [r.to_dict() for r in rows]}


@router.get("/{customer_id}/risk")
async def get_customer_risk(customer_id: str):
    from app.services.risk_service import check_risk
    return check_risk(customer_id)

# ============================================================
# 批量导入
# ============================================================
from fastapi import File, UploadFile
from typing import Dict as _Dict
from pydantic import BaseModel as _BaseModel


class ImportConfirmRequest(_BaseModel):
    token: str
    mapping: _Dict[str, str]


@router.post("/import/upload")
async def import_upload(file: UploadFile = File(...)):
    """上传 Excel/CSV，返回预览。"""
    from app.services.import_service import save_upload, preview
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="文件内容为空")

    token, path = save_upload(content, file.filename)
    try:
        result = preview(path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "token": token,
        "filename": file.filename,
        **result,
    }


@router.post("/import/confirm")
async def import_confirm(req: ImportConfirmRequest):
    """按 mapping 执行导入。"""
    from app.services.import_service import get_upload_path, do_import
    path = get_upload_path(req.token)
    if not path:
        raise HTTPException(status_code=404, detail="临时文件已过期，请重新上传")

    try:
        result = do_import(path, req.mapping)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # 导入完删掉临时文件
    try:
        os.remove(path)
    except Exception:
        pass

    return result


@router.get("/import/template")
async def import_template():
    """下载导入模板（xlsx）。"""
    from fastapi.responses import FileResponse
    from app.services.import_service import IMPORT_DIR

    tpl_path = IMPORT_DIR / "_template.xlsx"
    if not tpl_path.exists():
        # 生成模板
        try:
            import openpyxl
        except ImportError:
            raise HTTPException(status_code=500, detail="未安装 openpyxl")

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "客户导入"
        headers = ["客户姓名", "手机号", "邮箱", "地址", "VIP等级", "订单数", "退款数", "投诉数"]
        ws.append(headers)

        # 示例数据
        samples = [
            ["张先生", "13800138000", "zhang@example.com", "上海市浦东新区", "gold", 5, 1, 0],
            ["李女士", "13900139000", "li@example.com", "北京市海淀区", "normal", 2, 0, 0],
        ]
        for row in samples:
            ws.append(row)

        # 列宽
        for i, w in enumerate([14, 16, 26, 30, 10, 10, 10, 10], 1):
            ws.column_dimensions[chr(64 + i)].width = w

        wb.save(str(tpl_path))

    return FileResponse(
        str(tpl_path),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="客户导入模板.xlsx",
    )
