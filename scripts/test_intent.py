import sys, os
sys.path.insert(0, r"I:\XMWJ\PYxm\Enterprise After-Sales Knowledge Base Agent Platform")
os.chdir(r"I:\XMWJ\PYxm\Enterprise After-Sales Knowledge Base Agent Platform")

from app.intent.factory import get_intent_engine
from app.intent.core.engine import IntentEngine
from app.intent.core.types import Intent, IntentContext
from app.intent.core.matchers import register_matcher, BaseMatcher, list_matchers


engine = get_intent_engine()
print(f"[1] 加载意图: {engine.size} 条")
print(f"[1] 意图列表: {[i.id for i in engine.intents]}")
print(f"[1] 匹配器: {list_matchers()}")


def test(text, expect=None):
    top = engine.classify_top(text)
    all_m = engine.classify(text, top_k=3)
    print()
    print(f">>> {text}")
    if not top:
        print("  [无命中]")
        return
    print(f"  top1: {top.id:<12} score={top.score:.1f}  ({top.matched_value})")
    for m in all_m[1:]:
        print(f"  次:   {m.id:<12} score={m.score:.1f}  ({m.matched_value})")
    if expect and top.id != expect:
        print(f"  ⚠️  预期 {expect}, 实际 {top.id}")


print()
print("=" * 60)
print("意图识别测试")
print("=" * 60)

test("我要退货")
test("想换个新的")
test("什么时候退款到账")
test("我的设备 E102 报警了，帮我报修")
test("还在保修期内吗")
test("帮我开张发票")
test("订单到哪了")
test("快递什么时候到")
test("我要转人工")
test("太差了，我要投诉")
test("E102 报警怎么排查")     # 应该走 qa（无关键词命中）

# ============ 验证：注册自定义匹配器 ============
print()
print("=" * 60)
print("[10] 验证框架可扩展：注册自定义匹配器")
print("=" * 60)

class LengthMatcher(BaseMatcher):
    name = "length"
    def score(self, intent, ctx):
        # 演示：文本长度 > 20 时给所有意图 +5 分
        if len(ctx.text) > 20 and intent.keywords:
            return 5.0, "long_text"
        return 0.0, ""

register_matcher("length", LengthMatcher, override=True)
print("[OK] 自定义匹配器注册成功")

# 用内存引擎验证
e2 = IntentEngine(matcher=LengthMatcher())
e2.add_intent(Intent(id="test", name="测试", keywords=["测试"]))
r = e2.classify("这是一段超过二十个字的测试文本内容，用于验证自定义匹配器")
print(f"[OK] 内存引擎 + 自定义匹配器 -> {r[0].id if r else '无命中'} (score={r[0].score if r else 0})")

print()
print("=" * 60)
print("意图识别测试完成")
