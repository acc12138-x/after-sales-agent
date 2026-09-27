import sys, os
sys.path.insert(0, r"I:\XMWJ\PYxm\Enterprise After-Sales Knowledge Base Agent Platform")
os.chdir(r"I:\XMWJ\PYxm\Enterprise After-Sales Knowledge Base Agent Platform")

import json
from app.services.impl import order_mock, logistics_mock, product_mock, customer_mock
from app.services.registry import list_services, get_service
from app.services.facade import get_services


def p(title, obj):
    print()
    print("-" * 60)
    print(title)
    print("-" * 60)
    if isinstance(obj, (dict, list)):
        print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))
    else:
        print(obj)


print("[1] 已注册服务:", list_services())

svc = get_services()

# OrderService
order = svc.order.get_order("O20260101001")
p("用例1: 查订单 O20260101001", order)

days = svc.order.days_since_delivered("O20260101001")
p("用例2: 距离签收天数", days)

orders = svc.order.get_user_orders("U1001")
p("用例3: 用户 U1001 的订单数", len(orders))

# LogisticsService
logi = svc.logistics.get_tracking("O20260201002")
p("用例4: 查物流 O20260201002", logi)

# ProductService
prod = svc.product.get_product("XY200")
p("用例5: 查商品 XY200", prod)

warranty = svc.product.get_warranty_days("XY200")
p("用例6: XY200 保修天数", warranty)

is_special = svc.product.is_special_category("NEI001")
p("用例7: NEI001 是否特殊品类", is_special)

# CustomerService
cust = svc.customer.get_customer("U1001")
p("用例8: 查客户 U1001", cust)

vip = svc.customer.is_vip("U1001")
p("用例9: U1001 是否 VIP", vip)

# 验证：动态替换实现
print()
print("[10] 验证框架可替换（动态注册新的 order 服务）")

from app.services.base import BaseService

class FakeOrderService(BaseService):
    name = "order"
    def setup(self):
        super().setup()
    def get_order(self, order_id):
        return {"order_id": order_id, "status": "FAKE"}

from app.services.registry import ServiceRegistry
ServiceRegistry.register("order", FakeOrderService, override=True)
ServiceRegistry.reset()  # 清空缓存

svc2 = get_services()
p("用例10: 替换后查订单", svc2.order.get_order("O20260101001"))

print()
print("=" * 60)
print("业务服务层测试完成")
