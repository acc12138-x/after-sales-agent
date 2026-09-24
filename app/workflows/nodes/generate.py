
from __future__ import annotations
import re
from typing import Dict, List

from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from app.config.settings import get_settings
from app.workflows.state import AgentState

_LLM_LOCAL = None
_LLM_CLOUD = None

# ---------- 后处理正则 ----------
# 1. Qwen3 的思考块
THINK_BLOCK = re.compile(r"<think[^>]*>.*?</think[^>]*>", re.DOTALL | re.IGNORECASE)
THINK_TAG = re.compile(r"</?think[^>]*>", re.IGNORECASE)

# 2. 自问自答标记（遇到就截断）
STOP_MARKERS = [
    "用户问题：", "用户问题:",
    "用户提问：", "用户提问:",
    "问题：", "问题:",
    "答案：", "答案:",
    "参考来源：", "参考来源:",
    "注：", "注:",
    "请注意：", "请注意:",
    "**用户问题", "**答案",
]

# 3. 连续重复引用
REPEAT_CIT = re.compile(r"(\[\d+\]\s*){3,}")

# 4. 开头误加的"暂无相关依据"
LEADING_NO_INFO = re.compile(
    r"^\s*暂[无未][^。\n]*建议转人工[。\.]?\s*",
)

# 5. 方括号里的动作描述（小模型怪癖）
BRACKET_ACTION = re.compile(r"\[(检查|重启|更换|确认|排查|处理)[^\]]{0,30}\]")


def _strip_think(text: str) -> str:
    """去掉 Qwen3 的思考块。"""
    text = THINK_BLOCK.sub("", text)
    text = THINK_TAG.sub("", text)
    return text


def _truncate_at_marker(text: str) -> str:
    """遇到自问自答的标记就截断。"""
    earliest = len(text)
    for marker in STOP_MARKERS:
        idx = text.find(marker)
        if 0 < idx < earliest:
            earliest = idx
    return text[:earliest].rstrip()


def clean_answer(text: str) -> str:
    if not text:
        return text

    # 1. 去思考块
    text = _strip_think(text)

    # 2. 去自问自答
    text = _truncate_at_marker(text)

    # 3. 去开头误加
    text = LEADING_NO_INFO.sub("", text)

    # 4. 去方括号动作
    text = BRACKET_ACTION.sub("", text)

    # 5. 压重复引用
    text = REPEAT_CIT.sub(" ", text)

    # 6. 压缩空行
    text = re.sub(r"\n{2,}", "\n", text)

    # 7. 去掉行首尾多余空格
    text = "\n".join(line.strip() for line in text.splitlines())

    # 8. 硬截断
    text = text.strip()
    if len(text) > 250:
        text = text[:250].rstrip()

    return text


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
                max_tokens=300,
            )
        return _LLM_CLOUD

    if _LLM_LOCAL is None:
        _LLM_LOCAL = ChatOllama(
            model=s.ollama_llm_model,
            base_url=s.ollama_base_url,
            temperature=0.1,        # 低温度
            num_predict=200,        # 输出上限
            num_ctx=2048,           # 上下文窗口
            repeat_penalty=1.4,     # 重复惩罚
            top_p=0.85,
            top_k=30,
        )
    return _LLM_LOCAL


PROMPT = """你是一个企业售后助手。请根据下面的【知识片段】，用简洁的中文回答用户的问题。

【知识片段】
{context}

【用户问题】
{question}

【回答要求】
1. 只使用【知识片段】中的信息，绝对不能编造任何内容。
2. 直接给出答案。不要复述问题，不要输出"用户问题："或"答案："这样的标记。
3. 用 1-3 条短句回答，总字数不超过 80 字。
4. 每条结论后可以标注一次引用编号，格式如 [1]。不要连续标注多个引用。
5. 如果知识片段中没有相关信息，直接回答"暂无相关依据，建议转人工。"

【回答】"""


def format_context(chunks: List[Dict], max_chunks: int = 3) -> str:
    lines = []
    for i, c in enumerate(chunks[:max_chunks], 1):
        text = c.get("text", "").strip().replace("\n", " ")
        lines.append(f"[{i}] {text[:180]}")
    return "\n".join(lines)


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
    try:
        resp = get_llm(use_cloud=use_cloud).invoke(prompt)
        raw = resp.content if hasattr(resp, "content") else str(resp)
        answer = clean_answer(raw)
    except Exception as e:
        answer = f"生成失败：{e}"

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
