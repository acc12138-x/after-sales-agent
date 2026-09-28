"""风控服务：评估客户风险等级。"""
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Dict

from sqlalchemy import select

from app.db.models.customer import Customer
from app.db.models.refund import RefundRequest
from app.db.session import session_scope


RISK_RULES = [
    {"name": "高频退款", "weight": 30,
     "check": lambda c, ctx: c.total_refunds >= 3},
    {"name": "退款率高", "weight": 25,
     "check": lambda c, ctx: c.total_orders > 0 and c.total_refunds / max(c.total_orders, 1) >= 0.6},
    {"name": "多次投诉", "weight": 30,
     "check": lambda c, ctx: (c.total_complaints or 0) >= 2},
    {"name": "短期多退款", "weight": 25,
     "check": lambda c, ctx: ctx.get("recent_refunds", 0) >= 2},
    {"name": "低订单多退款", "weight": 15,
     "check": lambda c, ctx: c.total_orders <= 3 and c.total_refunds >= 3},
]


def check_risk(customer_id: str) -> Dict:
    """评估客户风险。返回 {level, score, reasons}。"""
    with session_scope() as s:
        c = s.get(Customer, customer_id)
        if c is None:
            return {"level": "unknown", "score": 0, "reasons": ["客户不存在"]}

        # 近 30 天退款次数
        cutoff = datetime.utcnow() - timedelta(days=30)
        recent = s.execute(
            select(RefundRequest).where(
                RefundRequest.customer_id == customer_id,
                RefundRequest.created_at >= cutoff,
            )
        ).scalars().all()

        ctx = {"recent_refunds": len(recent)}

        score = 0
        reasons = []
        for rule in RISK_RULES:
            try:
                if rule["check"](c, ctx):
                    score += rule["weight"]
                    reasons.append(rule["name"])
            except Exception:
                pass

        if score >= 70:
            level = "high_risk"
        elif score >= 40:
            level = "suspicious"
        else:
            level = "normal"

        # 写回客户
        c.risk_score = score
        c.risk_level = level

        return {"level": level, "score": score, "reasons": reasons,
                "customer_id": customer_id, "customer_name": c.name}


def auto_decision(customer_id: str, amount: float, refund_type: str = "refund_only") -> Dict:
    """AI 初审：给出建议（approve / reject / need_human）+ 置信度。"""
    risk = check_risk(customer_id)

    # 硬规则
    if risk["level"] == "high_risk":
        return {"suggestion": "need_human", "confidence": 0.3,
                "reason": f"高风险客户（{','.join(risk['reasons'])}），必须人工审批",
                "risk": risk}
    if risk["level"] == "suspicious":
        return {"suggestion": "need_human", "confidence": 0.5,
                "reason": "疑似风险客户，建议人工复核", "risk": risk}

    # 金额规则
    if amount <= 100:
        return {"suggestion": "approve", "confidence": 0.9,
                "reason": "小额退款且客户信用良好", "risk": risk}
    if amount <= 500:
        return {"suggestion": "approve", "confidence": 0.7,
                "reason": "中等金额，客户信用良好", "risk": risk}
    if amount <= 2000:
        return {"suggestion": "need_human", "confidence": 0.6,
                "reason": "金额 > 500，需人工确认", "risk": risk}
    return {"suggestion": "need_human", "confidence": 0.4,
            "reason": "大额退款，必须人工审批", "risk": risk}
