"""缓存服务测试。"""


class TestCacheService:
    def test_set_get_exact(self):
        from app.services.cache_service import CacheService
        c = CacheService()
        c.clear_all()
        c.set("测试问题", {"answer": "测试答案", "intent": "qa", "citations": []}, intent="qa")
        got = c.get_exact("测试问题")
        assert got is not None
        assert got["answer"] == "测试答案"

    def test_only_qa_cached(self):
        from app.services.cache_service import CacheService
        c = CacheService()
        c.clear_all()
        c.set("ticket请求", {"answer": "x"}, intent="ticket")
        assert c.get_exact("ticket请求") is None

    def test_stats(self):
        from app.services.cache_service import CacheService
        c = CacheService()
        c.clear_all()
        c.set("q1", {"answer": "a1"}, intent="qa")
        c.set("q2", {"answer": "a2"}, intent="qa")
        assert c.stats()["active_entries"] == 2

    def test_clear(self):
        from app.services.cache_service import CacheService
        c = CacheService()
        c.set("x", {"answer": "y"}, intent="qa")
        c.clear_all()
        assert c.get_exact("x") is None
