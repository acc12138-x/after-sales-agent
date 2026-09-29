"""意图识别测试。"""
from app.workflows.nodes.intent import _extract_slots, _is_consult_query


class TestSlotExtraction:
    def test_order_id(self):
        assert _extract_slots("订单 O20260101001 到哪了").get("order_id") == "O20260101001"

    def test_phone(self):
        assert _extract_slots("手机号 13800138000").get("phone") == "13800138000"

    def test_error_code(self):
        assert _extract_slots("E102 报警").get("error_code") == "E102"

    def test_device_model(self):
        assert _extract_slots("XY200 坏了").get("device_model") == "XY200"

    def test_amount(self):
        assert _extract_slots("退款 500 元").get("amount") == 500.0

    def test_error_code_as_device_fallback(self):
        assert _extract_slots("E102 报警").get("device_model") == "E102"


class TestConsultQuery:
    def test_how_to_troubleshoot(self):
        assert _is_consult_query("E102 报警怎么排查") is True

    def test_what_cause(self):
        assert _is_consult_query("E102 报警是什么原因") is True

    def test_action_word(self):
        assert _is_consult_query("帮我报修 E102") is False

    def test_order_related(self):
        assert _is_consult_query("订单到哪了") is False

    def test_pure_alarm_code(self):
        assert _is_consult_query("E503 安全门报警") is True

    def test_with_action_and_alarm(self):
        assert _is_consult_query("帮我修一下 E503 报警") is False
