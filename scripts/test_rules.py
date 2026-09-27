import sys, os
sys.path.insert(0, r"I:\XMWJ\PYxm\Enterprise After-Sales Knowledge Base Agent Platform")
os.chdir(r"I:\XMWJ\PYxm\Enterprise After-Sales Knowledge Base Agent Platform")

from app.rules.factory import get_engine, reload_engine
from app.rules.core.engine import RuleEngine
from app.rules.core.types import MatchOptions, Rule
from app.rules.core.operators import register_operator, list_operators


def show(title, matches):
    print()
    print("-" * 60)
    print(title)
    print("-" * 60)
    for m in matches:
        r = m.rule
        result = r.result
        print(f"  规则: {r.name}  (id={r.id}, priority={r.priority})")
        print(f"  结果: {result}")


# ============ 1. 框架能力：注册自定义操作符 ============
print("[1] 内置操作符:", list_operators())

register_operator("is_even", lambda a, _: isinstance(a, int) and a % 2 == 0, override=True)
print("[1] 注册后:", "is_even" in list_operators())

# ============ 2. 纯内存引擎（不依赖 YAML） ============
engine_mem = RuleEngine()
engine_mem.add_rule(Rule(
    id="demo_even",
    name="偶数命中",
    conditions=[{"field": "n", "op": "is_even"}],
    result={"msg": "n 是偶数"},
))
r = engine_mem.match({"n": 8}, MatchOptions(stop_on_first=True))
print()
print("[2] 内存引擎测试:", r[0].result if r else "无命中")

# ============ 3. 业务引擎（从 YAML 加载） ============
engine = get_engine("after_sales")
print()
print(f"[3] 售后引擎加载了 {engine.size} 条规则")

# 用例 1：签收 3 天 / 未使用 / 原包装 / 普通品类
show("用例1: 签收3天/未使用/原包装/普通品类",
     engine.match({
         "days_since_received": 3, "used": False,
         "has_original_package": True, "category": "家电",
         "quality_issue": False,
     }, MatchOptions(category="return", stop_on_first=True)))

# 用例 2：签收 10 天 / 有质量问题
show("用例2: 签收10天/有质量问题",
     engine.match({
         "days_since_received": 10, "used": True,
         "has_original_package": False, "category": "家电",
         "quality_issue": True,
     }, MatchOptions(category="return", stop_on_first=True)))

# 用例 3：签收 20 天 / 无问题
show("用例3: 签收20天/无问题",
     engine.match({
         "days_since_received": 20, "used": False,
         "has_original_package": True, "category": "家电",
         "quality_issue": False,
     }, MatchOptions(category="return", stop_on_first=True)))

# 用例 4：签收 3 天 / 特殊品类
show("用例4: 签收3天/特殊品类(内衣)",
     engine.match({
         "days_since_received": 3, "used": False,
         "has_original_package": True, "category": "内衣",
         "quality_issue": False,
     }, MatchOptions(category="return", stop_on_first=True)))

# 用例 5：保修期内 / 非人为
show("用例5: 保修期内/非人为损坏",
     engine.match({
         "days_since_purchase": 200, "human_damage": False,
     }, MatchOptions(category="warranty", stop_on_first=True)))

# 用例 6：超保修期
show("用例6: 超保修期",
     engine.match({
         "days_since_purchase": 500, "human_damage": False,
     }, MatchOptions(category="warranty", stop_on_first=True)))

# ============ 4. 验证：换一套规则数据 ============
print()
print("[4] 验证框架与业务分离（动态加规则）")
engine.add_rule(Rule(
    id="return_vip_extra_30days",
    name="VIP 用户额外延长 30 天",
    category="return",
    priority=110,
    conditions=[
        {"field": "user.vip", "op": "eq", "value": True},
        {"field": "days_since_received", "op": "le", "value": 45},
    ],
    result={"allowed": True, "message": "VIP 用户享受延长退货期"},
))
show("用例7: VIP 用户 / 签收 40 天",
     engine.match({
         "user": {"vip": True},
         "days_since_received": 40,
     }, MatchOptions(category="return", stop_on_first=True)))

print()
print("=" * 60)
print("规则引擎框架测试完成")
