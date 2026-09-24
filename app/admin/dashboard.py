
"""Streamlit 管理后台。"""
from __future__ import annotations

import os
import re
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost,::1")
os.environ.setdefault("no_proxy", "127.0.0.1,localhost,::1")

import streamlit as st
import httpx

FASTAPI = "http://127.0.0.1:8000"

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
</style>
""", unsafe_allow_html=True)


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


def api_get(path: str):
    try:
        r = httpx.get(FASTAPI + path, timeout=5, trust_env=False)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


# ============================================================
# 侧边栏
# ============================================================
with st.sidebar:
    st.title("🛠️ 售后助手")
    st.caption("Enterprise After-Sales Agent")
    st.divider()

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

    st.divider()
    # FastAPI 探活
    h = api_get("/health")
    if h:
        st.success("🟢 FastAPI 在线")
    else:
        st.error("🔴 FastAPI 离线")

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
            source = st.text_input("来源", value="manual")
            content = st.text_area("内容（Markdown）", height=200)
            submitted = st.form_submit_button("上传并索引", use_container_width=True, type="primary")

        if submitted and content.strip():
            with st.spinner("切片、向量化..."):
                try:
                    r = get_retriever()
                    from app.rag.chunking import chunk_document
                    chunks = chunk_document(content, doc_id=doc_id, source=source)
                    r.index_chunks(chunks)
                    st.success(f"✅ {len(chunks)} 个切片已入库")
                    time.sleep(0.5)
                    st.rerun()
                except Exception as e:
                    st.error(f"失败: {e}")

    with col2:
        st.subheader("📊 知识库统计")
        try:
            r = get_retriever()
            c1, c2, c3 = st.columns(3)
            c1.metric("总切片数", r.count())
            c2.metric("向量维度", 1024)
            c3.metric("嵌入模型", "bge-m3")

            st.divider()
            st.subheader("🔍 快速检索")
            query = st.text_input("检索问题", value="E102 报警")
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
                        f"[{i}] score={c.get('rerank_score', 0):.3f} · {c['metadata'].get('source','')}",
                        expanded=(i == 1)
                    ):
                        st.text(c["text"][:500])
        except Exception as e:
            st.error(f"失败: {e}")

# ============================================================
# Tab 2: 对话测试
# ============================================================
with tab_chat:
    st.subheader("💬 在线对话（直连 LangGraph）")

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

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("meta"):
                with st.expander("详情"):
                    st.json(msg["meta"])

    if prompt := st.chat_input("输入问题，比如：E102 报警怎么排查"):
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("思考中..."):
                t0 = time.time()
                try:
                    # 改走 HTTP，让所有业务在 FastAPI 进程里跑
                    r = httpx.post(
                        FASTAPI + "/chat",
                        json={
                            "message": prompt,
                            "thread_id": st.session_state.thread_id,
                            "user_id": "streamlit",
                        },
                        timeout=60,
                        trust_env=False,
                    )
                    resp = r.json()
                    final = {
                        "answer": resp.get("answer", ""),
                        "intent": resp.get("intent"),
                        "confidence": resp.get("confidence", 0.0),
                        "citations": resp.get("citations", []),
                        "flow_status": resp.get("flow_status"),
                        "hitl_pending": resp.get("hitl_pending", False),
                        "hitl_reason": resp.get("hitl_reason"),
                    }
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
# Tab 3: 工单（改走 HTTP API）
# ============================================================
with tab_ticket:
    st.subheader("🎫 工单管理")

    col_a, col_b = st.columns([3, 1])
    with col_b:
        if st.button("🔄 刷新", use_container_width=True):
            st.rerun()

    data = api_get("/tickets")

    if data is None:
        st.error("无法连接 FastAPI，请确认服务在运行")
    elif data.get("total", 0) == 0:
        st.info("暂无工单。去「对话测试」发一条 '帮我报修 E102 设备' 试试。")
    else:
        items = data.get("items", [])

        c1, c2, c3 = st.columns(3)
        c1.metric("总工单", len(items))
        c2.metric("已派单", sum(1 for t in items if t["status"] == "assigned"))
        c3.metric("待处理", sum(1 for t in items if t["status"] == "pending"))

        st.divider()

        import pandas as pd
        df = pd.DataFrame(items)
        cols_show = ["ticket_id", "status", "assigned_to", "device_model", "error_code", "created_at"]
        cols_show = [c for c in cols_show if c in df.columns]
        st.dataframe(df[cols_show], use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("工单详情")
        sel = st.selectbox("选择工单", [t["ticket_id"] for t in items])
        if sel:
            detail = api_get(f"/tickets/{sel}")
            if detail:
                st.json(detail)

# ============================================================
# Tab 4: 系统配置
# ============================================================
with tab_config:
    st.subheader("⚙️ 系统配置")

    env_path = ROOT / ".env"
    if env_path.exists():
        env_content = env_path.read_text(encoding="utf-8")

        cols = st.columns(2)
        with cols[0]:
            st.markdown("##### 模型")
            ollama_url = st.text_input("Ollama 地址", value=settings.ollama_base_url)
            llm_model = st.text_input("LLM 模型", value=settings.ollama_llm_model)
            embed_model = st.text_input("嵌入模型", value=settings.ollama_embedding_model)
            deepseek_key = st.text_input("DeepSeek Key", value="", type="password")

        with cols[1]:
            st.markdown("##### RAG 参数")
            chunk_size = st.number_input("Chunk", value=settings.chunk_size, min_value=128, max_value=2048)
            chunk_overlap = st.number_input("Overlap", value=settings.chunk_overlap, min_value=0, max_value=512)
            top_k_retrieve = st.number_input("召回 TopK", value=settings.top_k_retrieve, min_value=5, max_value=100)
            top_k_rerank = st.number_input("重排 TopK", value=settings.top_k_rerank, min_value=1, max_value=20)

        if st.button("💾 保存配置", type="primary"):
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
            st.success("✅ 已保存。需重启 FastAPI 生效。")

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

    c2.metric("服务状态", "运行中" if api_get("/health") else "离线")
    c3.metric("嵌入维度", 1024)

    import psutil
    try:
        c4.metric("内存", f"{psutil.Process().memory_info().rss/1024/1024:.0f} MB")
    except Exception:
        c4.metric("内存", "N/A")

    st.divider()
    st.markdown("**外部服务状态**")

    checks = [
        ("Ollama", "http://127.0.0.1:11434/api/tags"),
        ("FastAPI", "http://127.0.0.1:8000/health"),
    ]
    for name, url in checks:
        try:
            resp = httpx.get(url, timeout=3, trust_env=False)
            if resp.status_code == 200:
                st.write(f"**{name}** · ✅ {resp.status_code}")
            else:
                st.write(f"**{name}** · ⚠️ {resp.status_code}")
        except Exception as e:
            st.write(f"**{name}** · ❌ {e}")

    st.divider()
    st.markdown("**快捷操作**")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔄 清空会话", use_container_width=True):
            st.session_state.chat_history = []
            st.success("已清空")
    with c2:
        if st.button("🔥 重载缓存", use_container_width=True):
            st.cache_resource.clear()
            st.success("已清空")
