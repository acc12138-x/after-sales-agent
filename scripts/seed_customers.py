import os, sys
from datetime import datetime, timedelta
from pathlib import Path

# 项目根从脚本自身位置推导。
# 不要写死本机绝对路径 —— 那样在 Docker / 服务器上会 FileNotFoundError。
ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from sqlalchemy import select
from app.db.session import session_scope, init_db
from app.db.models.customer import Customer
from app.db.models.order import Order

init_db()

now = datetime.utcnow()

CUSTOMERS = [
    {"customer_id": "C1001", "name": "张先生", "phone": "13800138000", "vip_level": "gold", "risk_level": "normal", "total_orders": 5, "total_refunds": 1},
    {"customer_id": "C1002", "name": "李女士", "phone": "13900139000", "vip_level": "normal", "risk_level": "normal", "total_orders": 2, "total_refunds": 0},
    {"customer_id": "C1003", "name": "王先生", "phone": "13700137000", "vip_level": "normal", "risk_level": "suspicious", "total_orders": 3, "total_refunds": 4},
    {"customer_id": "C1004", "name": "赵女士", "phone": "13600136000", "vip_level": "silver", "risk_level": "normal", "total_orders": 8, "total_refunds": 1},
    {"customer_id": "C1005", "name": "钱先生", "phone": "13500135000", "vip_level": "normal", "risk_level": "high_risk", "total_orders": 2, "total_refunds": 7, "total_complaints": 3},
]

ORDERS = [
    # 张先生 5 单
    {"order_id": "O20260101001", "customer_id": "C1001", "product_sku": "XY200", "product_name": "XY200 智能设备", "category": "家电", "amount": 2999.00, "status": "delivered", "created_at": now - timedelta(days=45), "delivered_at": now - timedelta(days=42), "warranty_days": 365},
    {"order_id": "O20260101002", "customer_id": "C1001", "product_sku": "AB100", "product_name": "AB100 传感器", "category": "配件", "amount": 199.00, "status": "delivered", "created_at": now - timedelta(days=20), "delivered_at": now - timedelta(days=18), "warranty_days": 180},
    {"order_id": "O20260101003", "customer_id": "C1001", "product_sku": "E102-KIT", "product_name": "E102 故障套件", "category": "配件", "amount": 299.00, "status": "delivered", "created_at": now - timedelta(days=10), "delivered_at": now - timedelta(days=8), "warranty_days": 180},
    # 李女士 2 单
    {"order_id": "O20260102001", "customer_id": "C1002", "product_sku": "XY100", "product_name": "XY100 智能设备", "category": "家电", "amount": 1999.00, "status": "delivered", "created_at": now - timedelta(days=15), "delivered_at": now - timedelta(days=12), "warranty_days": 365},
    {"order_id": "O20260102002", "customer_id": "C1002", "product_sku": "NEI001", "product_name": "内衣套装", "category": "内衣", "amount": 599.00, "status": "delivered", "created_at": now - timedelta(days=5), "delivered_at": now - timedelta(days=3), "warranty_days": 0},
    # 王先生 3 单（风控）
    {"order_id": "O20260103001", "customer_id": "C1003", "product_sku": "XY200", "product_name": "XY200 智能设备", "category": "家电", "amount": 2999.00, "status": "refunded", "created_at": now - timedelta(days=30), "delivered_at": now - timedelta(days=28), "warranty_days": 365},
    {"order_id": "O20260103002", "customer_id": "C1003", "product_sku": "E098", "product_name": "E098 备件", "category": "配件", "amount": 99.00, "status": "refunded", "created_at": now - timedelta(days=15), "delivered_at": now - timedelta(days=13), "warranty_days": 90},
    {"order_id": "O20260103003", "customer_id": "C1003", "product_sku": "AB100", "product_name": "AB100 传感器", "category": "配件", "amount": 199.00, "status": "shipped", "created_at": now - timedelta(days=3), "warranty_days": 180},
    # 赵女士 8 单（简化）
    {"order_id": "O20260104001", "customer_id": "C1004", "product_sku": "XY300", "product_name": "XY300 旗舰设备", "category": "家电", "amount": 4999.00, "status": "delivered", "created_at": now - timedelta(days=60), "delivered_at": now - timedelta(days=58), "warranty_days": 730},
    # 钱先生 2 单（高风险）
    {"order_id": "O20260105001", "customer_id": "C1005", "product_sku": "AB100", "product_name": "AB100 传感器", "category": "配件", "amount": 199.00, "status": "refunded", "created_at": now - timedelta(days=25), "delivered_at": now - timedelta(days=23), "warranty_days": 180},
    {"order_id": "O20260105002", "customer_id": "C1005", "product_sku": "E102-KIT", "product_name": "E102 故障套件", "category": "配件", "amount": 299.00, "status": "refunded", "created_at": now - timedelta(days=10), "delivered_at": now - timedelta(days=8), "warranty_days": 180},
]

with session_scope() as s:
    for c in CUSTOMERS:
        exists = s.execute(select(Customer).where(Customer.customer_id == c["customer_id"])).scalar_one_or_none()
        if exists:
            continue
        s.add(Customer(**c))
    print(f"[ADD] {len(CUSTOMERS)} 客户")

    for o in ORDERS:
        exists = s.execute(select(Order).where(Order.order_id == o["order_id"])).scalar_one_or_none()
        if exists:
            continue
        s.add(Order(**o))
    print(f"[ADD] {len(ORDERS)} 订单")

print("[OK] seed 完成")
