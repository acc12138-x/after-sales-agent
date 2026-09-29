"""RAG 测试。"""
from app.rag.chunking import chunk_document


class TestChunking:
    def test_basic_chunking(self):
        doc = "# 标题\n\n## 小节1\n内容1\n\n## 小节2\n内容3"
        chunks = chunk_document(doc, doc_id="test-1")
        assert len(chunks) > 0
        parents = [c for c in chunks if c.is_parent]
        assert len(parents) >= 2

    def test_heading_path(self):
        doc = "# 设备E102\n\n## 排查步骤\n1. 检查接线\n2. 重启"
        chunks = chunk_document(doc, doc_id="test-2")
        parents = [c for c in chunks if c.is_parent]
        found = any("排查步骤" in p.metadata.get("heading_path", "") for p in parents)
        assert found

    def test_metadata(self):
        doc = "# A\n\n## B\n内容"
        chunks = chunk_document(doc, doc_id="meta-test", source="manual")
        for c in chunks:
            assert c.metadata.get("doc_id") == "meta-test"
            assert c.metadata.get("source") == "manual"
