
from __future__ import annotations
import re
from typing import Dict, List

from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from app.config.settings import get_settings
from app.workflows.state import AgentState

_LLM_LOCAL = None
_LLM_CLOUD = None

THINK_BLOCK = re.compile(r"<think[^>]*>.*?</think[^>]*>", re.DOTALL | re.IGNORECASE)
THINK_TAG = re.compile(r"</?think[^>]*>", re.IGNORECASE)

STOP_MARKERS = [
    "用户问题：", "用户问题:",
    "用户提问：", "用户提问:",
    "\n问题：", "\n问题:",
    "\n答案：", "\n答案:",
    "参考来源：", "参考来源:",
    "**用户问题", "**答案",
]

REPEAT_CIT = re.compile(r"(\[\d+\]\s*){3,}")
LEADING_NO_INFO = re.compile(r"^\s*暂[无未][^。\n]*建议转人工[。\.]?\s*")
BRACKET_ACTION = re.compile(r"\[(检查|重启|更换|确认|排查|处理)[^\]]{0,30}\]")
NO_INFO_KEYWORDS = ["暂无相关依据", "无法回答", "知识片段中没", "没有相关"]


def _strip_think(text: str) -> str:
    text = THINK_BLOCK.sub("", text)
    text = THINK_TAG.sub("", text)
    return text


def _truncate_at_marker(text: str) -> str:
    earliest = len(text)
    for marker in STOP_MARKERS:
        idx = text.find(marker)
        if 0 < idx < earliest:
            earliest = idx
    return text[:earliest].rstrip()


def clean_answer(text: str) -> str:
    if not text:
        return text
    text = _strip_think(text)
    text = _truncate_at_marker(text)
    text = LEADING_NO_INFO.sub("", text)
    text = BRACKET_ACTION.sub("", text)
    text = REPEAT_CIT.sub(" ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    text = text.strip()
    if len(text) > 250:
        text = text[:250].rstrip()
    return text


def _is_refusal(text: str) -> bool:
    """判断答案是否是模型过度保守的拒答。"""
    if not text or len(text.strip()) < 3:
        return True
    for kw in NO_INFO_KEYWORDS:
        if kw in text:
            return True
    return False


def get_llm(use_cloud: bool = False):
    global _LLM_LOCAL, _LLM_CLOUD
    s = get_settings()

    if use_cloud and s.deepseek_api_key:
        if _LLM_CLOUD is None:
            _LLM_CLOUD = ChatOpenAI(
                model=s.deepseek_model,
                api_key=s.deepseek_api_key,
                base_url=s.deepseek_base_url,
                temperature=0.1,
                timeout=30,
                max_tokens=400,
            )
        return _LLM_CLOUD

    if _LLM_LOCAL is None:
        _LLM_LOCAL = ChatOllama(
            model=s.ollama_llm_model,
            base_url=s.ollama_base_url,
            temperature=0.1,
            num_predict=600,
            num_ctx=2048,
            repeat_penalty=1.4,
            top_p=0.85,
            top_k=30,
        )
    return _LLM_LOCAL


PROMPT = """你是企业售后助手。下面的知识片段已经包含用户问题的相关信息，请基于它们回答。

【知识片段】
{context}

【用户问题】
{question}

要求：
1. 知识片段里一定有相关信息，请直接提取并回答。不要回答"暂无相关依据"。
2. 不要输出思考过程，不要复述问题。
3. 用 1-3 条短句，总字数 80 字以内。
4. 结论后标注引用一次，如 [1]。

回答："""


def format_context(chunks: List[Dict], max_chunks: int = 3) -> str:
    lines = []
    for i, c in enumerate(chunks[:max_chunks], 1):
        text = c.get("text", "").strip().replace("\n", " ")
        lines.append(f"[{i}] {text[:180]}")
    return "\n".join(lines)


def _fallback_from_chunks(chunks: List[Dict]) -> str:
    """当 LLM 拒答或空答案时，用最相关的检索片段兜底。"""
    if not chunks:
        return "暂无相关依据，建议转人工。"
    text = chunks[0]["text"].strip().replace("\n", " ")
    # 取前 150 字
    snippet = text[:150].rstrip()
    return f"{snippet} [1]"


def generate_node(state: AgentState) -> AgentState:
    s = get_settings()
    chunks = state.get("retrieved", []) or []
    question = state.get("user_input", "")

    if not chunks:
        return {
            **state,
            "answer": "暂无相关依据，建议转人工。",
            "citations": [],
            "flow_status": "rejected",
        }

    context = format_context(chunks, max_chunks=3)
    prompt = PROMPT.format(context=context, question=question)

    use_cloud = bool(s.deepseek_api_key)
    raw = ""
    answer = ""
    try:
        resp = get_llm(use_cloud=use_cloud).invoke(prompt)
        raw = resp.content if hasattr(resp, "content") else str(resp)
        answer = clean_answer(raw)
    except Exception as e:
        answer = f"生成失败：{e}"

    # === 关键 fallback：模型拒答或空答案时，用检索片段兜底 ===
    if _is_refusal(answer):
        answer = _fallback_from_chunks(chunks)

    citations = [
        {"index": i + 1, "chunk_id": c["chunk_id"], "source": c["metadata"].get("source", "")}
        for i, c in enumerate(chunks[:3])
    ]

    messages = state.get("messages", []) or []
    messages = messages + [{"role": "assistant", "content": answer}]

    return {
        **state,
        "answer": answer,
        "citations": citations,
        "messages": messages,
        "flow_status": "succeeded",
    }
