
"""Streamlit 管理后台：知识库、对话、工单、配置、监控。"""
from __future__ import annotations

import os
import sys
import time
import json
import uuid
import re
from pathlib import Path
from datetime import datetime

# 让 Streamlit 能 import app.*
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost,::1")

import streamlit as st

# ============================================================
# 页面配置
# ============================================================
st.set_page_config(
    page_title="售后助手管理后台",
    page_icon="🛠️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .block-container { padding-top: 2rem; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        height: 44px; padding: 0 20px; border-radius: 8px;
        background: #f0f2f6; font-weight: 500;
    }
    .stTabs [aria-selected="true"] { background: #4f46e5; color: white; }
    .metric-card {
        background: white; padding: 1.2rem; border-radius: 10px;
        border-left: 4px solid #4f46e5; box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# 初始化（延迟 import 重量级模块）
# ============================================================
@st.cache_resource
def get_graph():
    from app.workflows.graph import graph
    return graph

@st.cache_resource
def get_retriever():
    from app.workflows.nodes.rag_search import get_retriever as _get
    return _get()

def get_settings():
    from app.config.settings import get_settings as _get
    return _get()

# ============================================================
# 侧边栏
# ============================================================
with st.sidebar:
    st.title("🛠️ 售后助手")
    st.caption("Enterprise After-Sales Agent")
    st.divider()

    # 系统状态
    try:
        settings = get_settings()
        st.success("✅ 后端已连接")
    except Exception as e:
        st.error(f"❌ 后端未连接: {e}")
        st.stop()

    st.divider()
    st.markdown("**当前配置**")
    st.caption(f"模型: `{settings.ollama_llm_model}`")
    st.caption(f"嵌入: `{settings.ollama_embedding_model}`")
    st.caption(f"云端 Key: `{'已配置' if settings.deepseek_api_key else '未配置'}`")
    st.caption(f"Chunk: {settings.chunk_size} / overlap {settings.chunk_overlap}")

# ============================================================
# 主页面
# ============================================================
st.title("企业售后知识库管理后台")

tab_kb, tab_chat, tab_ticket, tab_config, tab_monitor = st.tabs([
    "📚 知识库", "💬 对话测试", "🎫 工单", "⚙️ 系统配置", "📊 监控"
])

# ============================================================
# Tab 1: 知识库
# ============================================================
with tab_kb:
    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("📤 上传文档")
        with st.form("upload_form", clear_on_submit=True):
            doc_id = st.text_input("文档 ID", value=f"doc-{uuid.uuid4().hex[:6]}")
            source = st.text_input("来源（部门/手册名）", value="manual")
            content = st.text_area("文档内容（Markdown）", height=200, placeholder="# 标题\n\n## 小节\n内容...")
            submitted = st.form_submit_button("上传并索引", use_container_width=True, type="primary")

        if submitted and content.strip():
            with st.spinner("正在切片、向量化..."):
                try:
                    from app.rag.chunking import chunk_document
                    r = get_retriever()
                    chunks = chunk_document(content, doc_id=doc_id, source=source)
                    r.index_chunks(chunks)
                    st.success(f"✅ 上传成功：{len(chunks)} 个切片")
                    time.sleep(0.5)
                    st.rerun()
                except Exception as e:
                    st.error(f"上传失败: {e}")

        st.divider()
        st.subheader("🗑️ 删除文档")
        del_id = st.text_input("要删除的文档 ID")
        if st.button("删除", use_container_width=True):
            st.warning("删除功能开发中，请直接删除 data/chroma 目录")

    with col2:
        st.subheader("📊 知识库统计")
        try:
            r = get_retriever()
            total = r.count()

            c1, c2, c3 = st.columns(3)
            c1.metric("总切片数", total)
            c2.metric("向量维度", 1024)
            c3.metric("嵌入模型", "bge-m3")

            st.divider()
            st.subheader("🔍 快速检索测试")
            query = st.text_input("输入问题检索", value="E102 报警")
            if query:
                with st.spinner("检索中..."):
                    from app.rag.reranker import rerank
                    s = get_settings()
                    hits = r.search_hybrid(query, k=s.top_k_retrieve)
                    ids = [cid for cid, _ in hits]
                    cands = r.fetch_chunks(ids)
                    parents = r.expand_to_parents(ids)
                    seen = {c["chunk_id"] for c in cands}
                    pool = cands + [p for p in parents if p["chunk_id"] not in seen]
                    reranked = rerank(query, pool, top_k=5)

                for i, c in enumerate(reranked, 1):
                    with st.expander(
                        f"[{i}] score={c.get('rerank_score', 0):.3f} · {c['metadata'].get('source', '')}",
                        expanded=(i == 1)
                    ):
                        st.text(c["text"][:500])
                        st.caption(f"chunk_id: {c['chunk_id']}")
        except Exception as e:
            st.error(f"读取失败: {e}")

# ============================================================
# Tab 2: 对话测试
# ============================================================
with tab_chat:
    st.subheader("💬 在线对话（直连 LangGraph，不走飞书）")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = f"web-{uuid.uuid4().hex[:8]}"

    col_left, col_right = st.columns([3, 1])
    with col_right:
        st.caption(f"Thread: `{st.session_state.thread_id}`")
        if st.button("🔄 新会话", use_container_width=True):
            st.session_state.chat_history = []
            st.session_state.thread_id = f"web-{uuid.uuid4().hex[:8]}"
            st.rerun()

    # 显示历史
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("meta"):
                with st.expander("详情"):
                    st.json(msg["meta"])

    # 输入框
    if prompt := st.chat_input("输入问题，比如：E102 报警怎么排查"):
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("思考中..."):
                t0 = time.time()
                try:
                    g = get_graph()
                    init = {
                        "thread_id": st.session_state.thread_id,
                        "user_input": prompt,
                        "messages": [],
                        "slots": {},
                    }
                    cfg = {"configurable": {"thread_id": st.session_state.thread_id}}
                    final = g.invoke(init, config=cfg)
                    dt = time.time() - t0

                    answer = final.get("answer") or "暂无相关依据，建议转人工。"
                    if final.get("hitl_pending"):
                        answer = f"**【需要人工确认】** {final.get('hitl_reason')}"

                    st.markdown(answer)
                    st.caption(f"⏱️ {dt:.2f}s · 意图: {final.get('intent')} · 置信度: {final.get('confidence', 0):.3f}")

                    meta = {
                        "intent": final.get("intent"),
                        "confidence": final.get("confidence"),
                        "citations": final.get("citations"),
                        "flow_status": final.get("flow_status"),
                        "hitl_pending": final.get("hitl_pending"),
                        "elapsed": round(dt, 3),
                    }
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": answer,
                        "meta": meta,
                    })
                except Exception as e:
                    st.error(f"出错: {e}")

# ============================================================
# Tab 3: 工单
# ============================================================
with tab_ticket:
    st.subheader("🎫 工单管理")

    try:
        from app.api.routes.tickets import _TICKETS

        if not _TICKETS:
            st.info("暂无工单。去「对话测试」里发一条 '帮我报修 E102' 试试。")
        else:
            c1, c2, c3 = st.columns(3)
            c1.metric("总工单", len(_TICKETS))
            c2.metric("已派单", sum(1 for t in _TICKETS.values() if t["status"] == "assigned"))
            c3.metric("待处理", sum(1 for t in _TICKETS.values() if t["status"] == "pending"))

            st.divider()

            import pandas as pd
            df = pd.DataFrame(list(_TICKETS.values()))
            st.dataframe(
                df[["ticket_id", "status", "assigned_to", "device_model", "error_code", "created_at"]],
                use_container_width=True,
                hide_index=True,
            )

            st.divider()
            st.subheader("工单详情")
            sel = st.selectbox("选择工单", list(_TICKETS.keys()))
            if sel:
                st.json(_TICKETS[sel])
    except Exception as e:
        st.error(f"读取工单失败: {e}")

# ============================================================
# Tab 4: 系统配置
# ============================================================
with tab_config:
    st.subheader("⚙️ 系统配置")

    env_path = ROOT / ".env"
    if env_path.exists():
        env_content = env_path.read_text(encoding="utf-8")

        st.markdown("**当前配置（只读，改完直接写 .env）**")

        # 常用配置可视化编辑
        cols = st.columns(2)

        with cols[0]:
            st.markdown("##### 模型")
            ollama_url = st.text_input("Ollama 地址", value="http://127.0.0.1:11434")
            llm_model = st.text_input("LLM 模型", value=settings.ollama_llm_model)
            embed_model = st.text_input("嵌入模型", value=settings.ollama_embedding_model)
            deepseek_key = st.text_input("DeepSeek API Key（可留空）", value="", type="password")

        with cols[1]:
            st.markdown("##### RAG 参数")
            chunk_size = st.number_input("Chunk 大小", value=settings.chunk_size, min_value=128, max_value=2048)
            chunk_overlap = st.number_input("Chunk overlap", value=settings.chunk_overlap, min_value=0, max_value=512)
            top_k_retrieve = st.number_input("召回 TopK", value=settings.top_k_retrieve, min_value=5, max_value=100)
            top_k_rerank = st.number_input("重排 TopK", value=settings.top_k_rerank, min_value=1, max_value=20)

        if st.button("💾 保存配置", type="primary"):
            import re
            new_env = env_content
            replacements = {
                "OLLAMA_BASE_URL": ollama_url,
                "OLLAMA_LLM_MODEL": llm_model,
                "OLLAMA_EMBEDDING_MODEL": embed_model,
                "CHUNK_SIZE": str(chunk_size),
                "CHUNK_OVERLAP": str(chunk_overlap),
                "TOP_K_RETRIEVE": str(top_k_retrieve),
                "TOP_K_RERANK": str(top_k_rerank),
            }
            if deepseek_key:
                replacements["DEEPSEEK_API_KEY"] = deepseek_key

            for k, v in replacements.items():
                new_env = re.sub(rf"^{k}=.*$", f"{k}={v}", new_env, flags=re.MULTILINE)

            env_path.write_text(new_env, encoding="utf-8", newline="\n")
            st.success("✅ 已保存。需要重启 FastAPI 生效。")
            st.code("Ctrl+C 停止 uvicorn，然后重新执行：\nuvicorn app.main:app --host 127.0.0.1 --port 8000")

        st.divider()
        with st.expander("查看完整 .env（脱敏）"):
            masked = re.sub(r"(API_KEY|SECRET|TOKEN)=.+", r"\1=***", env_content)
            st.code(masked, language="bash")
    else:
        st.error(".env 不存在")

# ============================================================
# Tab 5: 监控
# ============================================================
with tab_monitor:
    st.subheader("📊 运行监控")

    c1, c2, c3, c4 = st.columns(4)
    try:
        r = get_retriever()
        c1.metric("知识库切片", r.count())
    except Exception:
        c1.metric("知识库切片", "N/A")

    c2.metric("服务状态", "运行中")
    c3.metric("嵌入维度", 1024)

    import psutil
    try:
        c4.metric("内存使用", f"{psutil.Process().memory_info().rss / 1024 / 1024:.0f} MB")
    except Exception:
        c4.metric("内存使用", "N/A")

    st.divider()
    st.markdown("**外部服务状态**")

    checks = [
        ("Ollama", "http://127.0.0.1:11434/api/tags"),
        ("FastAPI", "http://127.0.0.1:8000/health"),
        ("Chroma", f"file://{settings.chroma_persist_dir}"),
    ]

    import httpx
    for name, url in checks:
        if url.startswith("file://"):
            st.write(f"**{name}** · 本地目录 · ✅")
            continue
        try:
            resp = httpx.get(url, timeout=3, trust_env=False)
            if resp.status_code == 200:
                st.write(f"**{name}** · {url} · ✅ {resp.status_code}")
            else:
                st.write(f"**{name}** · {url} · ⚠️ {resp.status_code}")
        except Exception as e:
            st.write(f"**{name}** · {url} · ❌ {e}")

    st.divider()
    st.markdown("**快捷操作**")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔄 清空会话历史", use_container_width=True):
            st.session_state.chat_history = []
            st.success("已清空")
    with c2:
        if st.button("🔥 重新加载模型缓存", use_container_width=True):
            st.cache_resource.clear()
            st.success("已清空缓存")
