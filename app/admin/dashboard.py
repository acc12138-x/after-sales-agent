
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
    st.markdown("**当前配置（实时）**")

    # 通过 HTTP 读 FastAPI 的 .env 最新值，避免进程内缓存
    _cfg_resp = api_get("/admin/config") or {}
    _cfg = _cfg_resp.get("config", {})

    if _cfg:
        st.caption(f"LLM Provider: `{_cfg.get('LLM_PROVIDER', 'ollama')}`")
        _llm_model = _cfg.get("OLLAMA_LLM_MODEL") if _cfg.get("LLM_PROVIDER") == "ollama" else _cfg.get("DEEPSEEK_MODEL")
        st.caption(f"模型: `{_llm_model or '未配置'}`")
        st.caption(f"嵌入: `{_cfg.get('OLLAMA_EMBEDDING_MODEL', 'bge-m3')}`")
        _has_key = bool(_cfg.get("DEEPSEEK_API_KEY") and _cfg["DEEPSEEK_API_KEY"] != "***")
        st.caption(f"云端 Key: `{'已配置' if _has_key else '未配置'}`")
        st.caption(f"Chunk: {_cfg.get('CHUNK_SIZE') or 512} / overlap {_cfg.get('CHUNK_OVERLAP') or 64}")
    else:
        # 退化到本地 settings
        st.caption(f"模型: `{settings.ollama_llm_model}`")
        st.caption(f"嵌入: `{settings.ollama_embedding_model}`")

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
    st.subheader("⚙️ 系统配置（热重载）")

    # 拉取可选项
    prov = api_get("/admin/providers") or {}
    cfg_resp = api_get("/admin/config") or {}
    cfg = cfg_resp.get("config", {})

    st.markdown("##### 🧠 模型 Provider")

    col1, col2 = st.columns(2)

    with col1:
        llm_opts = [p["value"] for p in prov.get("llm_providers", [])] or ["ollama", "deepseek"]
        llm_labels = {p["value"]: p["label"] for p in prov.get("llm_providers", [])}
        cur_llm = cfg.get("LLM_PROVIDER", "ollama")
        llm_provider = st.selectbox(
            "LLM Provider",
            options=llm_opts,
            index=llm_opts.index(cur_llm) if cur_llm in llm_opts else 0,
            format_func=lambda x: llm_labels.get(x, x),
        )

        if llm_provider == "ollama":
            ollama_models = prov.get("ollama_models_available", [])
            cur_model = cfg.get("OLLAMA_LLM_MODEL", "")
            default_idx = ollama_models.index(cur_model) if cur_model in ollama_models else 0
            llm_model = st.selectbox("Ollama 模型", options=ollama_models, index=default_idx) if ollama_models else st.text_input("模型名", value=cur_model)
        else:
            ds_models = prov.get("deepseek_models", ["deepseek-chat"])
            cur_model = cfg.get("DEEPSEEK_MODEL", "deepseek-chat")
            llm_model = st.selectbox("DeepSeek 模型", options=ds_models,
                                     index=ds_models.index(cur_model) if cur_model in ds_models else 0)
            deepseek_key = st.text_input(
                "DeepSeek API Key",
                value=cfg.get("DEEPSEEK_API_KEY", ""),
                type="password",
                help="留空则不更新已保存的 key",
            )

    with col2:
        emb_opts = [p["value"] for p in prov.get("embedding_providers", [])] or ["ollama", "dashscope"]
        emb_labels = {p["value"]: p["label"] for p in prov.get("embedding_providers", [])}
        cur_emb = cfg.get("EMBEDDING_PROVIDER", "ollama")
        emb_provider = st.selectbox(
            "Embedding Provider",
            options=emb_opts,
            index=emb_opts.index(cur_emb) if cur_emb in emb_opts else 0,
            format_func=lambda x: emb_labels.get(x, x),
        )

        if emb_provider == "ollama":
            emb_models = prov.get("ollama_embedding_available", [])
            cur_emb_model = cfg.get("OLLAMA_EMBEDDING_MODEL", "")
            idx = emb_models.index(cur_emb_model) if cur_emb_model in emb_models else 0
            emb_model = st.selectbox("Ollama 嵌入模型", options=emb_models, index=idx) if emb_models else st.text_input("嵌入模型名", value=cur_emb_model)
        else:
            ds_emb = prov.get("dashscope_models", ["text-embedding-v3"])
            cur_emb_model = cfg.get("DASHSCOPE_EMBEDDING_MODEL", "text-embedding-v3")
            emb_model = st.selectbox("DashScope 嵌入模型", options=ds_emb,
                                     index=ds_emb.index(cur_emb_model) if cur_emb_model in ds_emb else 0)
            dash_key = st.text_input(
                "DashScope API Key",
                value=cfg.get("DASHSCOPE_API_KEY", ""),
                type="password",
            )

    st.divider()
    st.markdown("##### 🔧 RAG 参数")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        chunk_size = st.number_input("Chunk Size", value=int(cfg.get("CHUNK_SIZE") or 512), min_value=128, max_value=2048)
    with c2:
        chunk_overlap = st.number_input("Overlap", value=int(cfg.get("CHUNK_OVERLAP") or 64), min_value=0, max_value=512)
    with c3:
        top_k_retrieve = st.number_input("召回 TopK", value=int(cfg.get("TOP_K_RETRIEVE") or 20), min_value=5, max_value=100)
    with c4:
        top_k_rerank = st.number_input("重排 TopK", value=int(cfg.get("TOP_K_RERANK") or 5), min_value=1, max_value=20)

    st.divider()

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        if st.button("💾 保存配置", type="primary", use_container_width=True):
            updates = {
                "LLM_PROVIDER": llm_provider,
                "EMBEDDING_PROVIDER": emb_provider,
                "CHUNK_SIZE": str(chunk_size),
                "CHUNK_OVERLAP": str(chunk_overlap),
                "TOP_K_RETRIEVE": str(top_k_retrieve),
                "TOP_K_RERANK": str(top_k_rerank),
            }
            if llm_provider == "ollama":
                updates["OLLAMA_LLM_MODEL"] = llm_model
            else:
                updates["DEEPSEEK_MODEL"] = llm_model
                if deepseek_key:
                    updates["DEEPSEEK_API_KEY"] = deepseek_key

            if emb_provider == "ollama":
                updates["OLLAMA_EMBEDDING_MODEL"] = emb_model
            else:
                updates["DASHSCOPE_EMBEDDING_MODEL"] = emb_model
                if dash_key:
                    updates["DASHSCOPE_API_KEY"] = dash_key

            with st.spinner("保存中..."):
                try:
                    r = httpx.post(FASTAPI + "/admin/config",
                                   json={"values": updates},
                                   timeout=10, trust_env=False)
                    if r.status_code == 200:
                        st.success(f"✅ 已保存 {len(updates)} 项")
                        st.rerun()
                    else:
                        st.error(f"保存失败: {r.status_code} {r.text}")
                except Exception as e:
                    st.error(f"请求失败: {e}")

    with col_b:
        if st.button("🔥 热重载引擎", use_container_width=True):
            with st.spinner("重载中..."):
                try:
                    r = httpx.post(FASTAPI + "/admin/reload", timeout=30, trust_env=False)
                    if r.status_code == 200:
                        data = r.json()
                        st.success("✅ " + " / ".join(data.get("components", [])))
                    else:
                        st.error(f"重载失败: {r.status_code}")
                except Exception as e:
                    st.error(f"请求失败: {e}")

    with col_c:
        if st.button("🔄 保存并重载", use_container_width=True, type="secondary"):
            st.info("请先点【保存配置】，再点【热重载引擎】")

    st.divider()

    with st.expander("📄 当前 .env（脱敏）"):
        try:
            r = httpx.get(FASTAPI + "/admin/config", timeout=5, trust_env=False)
            data = r.json().get("config", {})
            for k, v in data.items():
                st.text(f"{k} = {v}")
        except Exception as e:
            st.error(f"读取失败: {e}")

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
