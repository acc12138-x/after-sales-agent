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

# Qwen3 思考痕迹的触发标记：遇到就截断
STOP_MARKERS = [
    "根据知识片段", "根据上述分析", "根据以上分析", "根据提供的",
    "用户问题：", "用户问题:", "用户提问：", "用户提问:",
    "\n问题：", "\n问题:", "\n答案：", "\n答案:",
    "参考来源：", "参考来源:", "参考:", "参考资料:",
    "**用户问题", "**答案",
    "\n备注：", "\n备注:", "\n注：", "\n注:",
    "回答：", "回答:",
    "总结：", "总结:",
]

REPEAT_CIT = re.compile(r"(\[\d+\]\s*){2,}")
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




# ============================================================
# 输出规范化：修复中英混杂 + 空格乱入 + 常见术语
# ============================================================
TERM_MAP = {
    "temperature": "温度",
    "sensor": "传感器",
    "device": "设备",
    "restart": "重启",
    "check": "检查",
    "warning": "报警",
    "error": "故障",
    "code": "代码",
    "power": "电源",
    "module": "模块",
    "connection": "接线",
    "wire": "接线",
}

# 中英之间不加空格，让 terms 直接替换
_SPACE_IN_CJK = re.compile(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])")
_CJK_EN_BOUNDARY = re.compile(r"([\u4e00-\u9fff])\s+([A-Za-z])")
_EN_CJK_BOUNDARY = re.compile(r"([A-Za-z])\s+([\u4e00-\u9fff])")


def _normalize_text(text: str) -> str:
    if not text:
        return text
    # 1) 术语英->中
    for en, zh in TERM_MAP.items():
        text = re.sub(rf"\b{en}\b", zh, text, flags=re.IGNORECASE)
    # 2) 去掉中文之间的多余空格
    for _ in range(3):
        new = _SPACE_IN_CJK.sub("", text)
        if new == text:
            break
        text = new
    # 3) 去掉中文和英文之间的空格（只在一侧是单个字符时，避免破坏正常词）
    text = _CJK_EN_BOUNDARY.sub(r"\1\2", text)
    text = _EN_CJK_BOUNDARY.sub(r"\1\2", text)
    # 4) 压缩连续空格
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text




def _dedup_citations(text: str) -> str:
    """同一编号的引用只保留第一次出现，后续删除。"""
    if not text:
        return text
    seen = set()

    def _repl(m):
        num = m.group(1)
        if num in seen:
            return ""
        seen.add(num)
        return m.group(0)

    text = re.sub(r"\[(\d+)\]", _repl, text)
    # 清理因删除引用产生的空格
    text = re.sub(r"\s+([。，；：！？、])", r"\1", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()

def clean_answer(text: str) -> str:
    if not text:
        return text
    text = _strip_think(text)
    text = _truncate_at_marker(text)
    text = LEADING_NO_INFO.sub("", text)
    text = BRACKET_ACTION.sub("", text)
    text = REPEAT_CIT.sub(" ", text)
    # 去掉开头的 "[1]." "[2]" 这类引用前缀
    text = re.sub(r"^\[\d+\][.、:：\s]*", "", text)
    text = re.sub(r"\n{2,}", "\n", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    text = text.strip()
    text = _normalize_text(text)
    text = _dedup_citations(text)
    if len(text) > 250:
        text = text[:250].rstrip()
    return text


def _is_refusal(text: str) -> bool:
    if not text or len(text.strip()) < 3:
        return True
    for kw in NO_INFO_KEYWORDS:
        if kw in text:
            return True
    return False


def _should_use_cloud() -> bool:
    s = get_settings()
    return s.llm_provider == "deepseek" and bool(s.deepseek_api_key)


def get_llm(use_cloud: bool = False):
    global _LLM_LOCAL, _LLM_CLOUD
    s = get_settings()

    if _should_use_cloud():
        use_cloud = True

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


PROMPT = """你是企业售后助手。根据下面的知识片段，用简洁中文回答用户问题。

【知识片段】
{context}

【用户问题】
{question}

规则：
1. 只使用知识片段中的信息。
2. 全部用中文回答，禁止出现英文单词。
3. 直接给出答案，不要复述问题，不要输出思考过程。
4. 用 1-3 条短句，总字数 80 字以内。
5. 结论后只标注一次引用，例如 [1]，不要重复标注。
6. 不要在末尾加"总结"或"备注"。

【回答】"""


def format_context(chunks: List[Dict], max_chunks: int = 3) -> str:
    lines = []
    for i, c in enumerate(chunks[:max_chunks], 1):
        text = c.get("text", "").strip().replace("\n", " ")
        lines.append(f"[{i}] {text[:180]}")
    return "\n".join(lines)


def _fallback_from_chunks(chunks: List[Dict]) -> str:
    if not chunks:
        return "暂无相关依据，建议转人工。"
    text = chunks[0]["text"].strip().replace("\n", " ")
    return f"{text[:150].rstrip()} [1]"


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

    answer = ""
    try:
        resp = get_llm(use_cloud=_should_use_cloud()).invoke(prompt)
        raw = resp.content if hasattr(resp, "content") else str(resp)
        answer = clean_answer(raw)
    except Exception as e:
        answer = f"生成失败：{e}"

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
