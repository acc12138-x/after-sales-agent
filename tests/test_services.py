"""业务服务测试。"""
from app.services.code_validator import validate_code, build_warning


class TestCodeValidator:
    def test_known_code(self):
        r = validate_code("E102")
        assert r["known"] is True
        assert r["valid"] is True

    def test_unknown_code(self):
        r = validate_code("E300")
        assert r["known"] is False
        assert isinstance(r["candidates"], list)

    def test_empty_code(self):
        r = validate_code("")
        assert r["known"] is False

    def test_case_insensitive(self):
        r = validate_code("e102")
        assert r["known"] is True
        assert r["code"] == "E102"

    def test_build_warning_known(self):
        r = validate_code("E102")
        assert build_warning("E102", r) == ""

    def test_build_warning_unknown(self):
        r = validate_code("E999")
        w = build_warning("E999", r)
        assert len(w) > 0
