"""生成节点：LLM 调用 + 多层输出后处理。"""
from __future__ import annotations
import re
from typing import Dict, List

from app.config.settings import get_settings
from app.workflows.state import AgentState

_LLM_CACHE = None

# ============================================================
# 常量
# ============================================================
THINK_BLOCK = re.compile(r"<think[^>]*>.*?</think[^>]*>", re.DOTALL | re.IGNORECASE)
THINK_TAG = re.compile(r"</?think[^>]*>", re.IGNORECASE)
PREFIX_RE = re.compile(r"^\s*\[[^\]]{1,80}\]\s*")

TITLE_WORDS = [
    "适用范围", "排查步骤", "故障现象", "解决方法", "注意事项",
    "操作步骤", "问题描述", "原因分析", "处理建议", "参考来源",
]

STOP_MARKERS = [
    "根据知识片段", "根据上述分析", "根据以上分析", "根据提供的",
    "用户问题：", "用户问题:", "用户提问：", "用户提问:",
    "\n问题：", "\n问题:", "\n答案：", "\n答案:",
    "参考来源：", "参考来源:",
    "**用户问题", "**答案",
    "\n备注：", "\n备注:", "\n注：", "\n注:",
    "回答：", "回答:", "总结：", "总结:",
]

REPEAT_CIT = re.compile(r"(\[\d+\]\s*){2,}")
LEADING_NO_INFO = re.compile(r"^\s*暂[无未][^。\n]*建议转人工[。\.]?\s*")
BRACKET_ACTION = re.compile(r"\[(检查|重启|更换|确认|排查|处理)[^\]]{0,30}\]")
NO_INFO_KEYWORDS = ["暂无相关依据", "无法回答", "知识片段中没", "没有相关"]

TERM_MAP = {
    "temperature": "温度", "temp": "温度", "sensor": "传感器",
    "device": "设备", "equipment": "设备", "module": "模块",
    "board": "主板", "chip": "芯片", "motor": "电机",
    "battery": "电池", "fan": "风扇", "power": "电源",
    "supply": "供电", "connector": "接口", "wire": "接线",
    "cable": "线缆", "connection": "接线", "switch": "开关",
    "button": "按钮", "display": "显示", "screen": "屏幕",
    "panel": "面板", "light": "指示灯", "valve": "阀门",
    "pump": "泵", "filter": "滤芯",
    "warning": "报警", "alert": "告警", "alarm": "报警",
    "error": "故障", "fault": "故障", "failure": "故障",
    "code": "代码", "issue": "问题", "problem": "问题",
    "abnormal": "异常", "normal": "正常", "broken": "损坏",
    "still": "仍然", "again": "再次",
    "check": "检查", "inspect": "检查", "verify": "确认",
    "restart": "重启", "reboot": "重启", "reset": "复位",
    "replace": "更换", "change": "更换", "swap": "更换",
    "clean": "清洁", "adjust": "调整", "calibrate": "校准",
    "step": "步骤", "solution": "解决方案", "cause": "原因",
}

TRAD_TO_SIMPLE = {
    "啟": "启", "動": "动", "後": "后", "體": "体", "溫": "温",
    "傳": "传", "檢": "检", "線": "线", "設": "设", "備": "备",
    "換": "换", "錯": "错", "誤": "误", "報": "报", "題": "题",
    "問": "问", "決": "决", "處": "处", "確": "确", "認": "认",
    "試": "试", "開": "开", "關": "关", "調": "调", "節": "节",
    "電": "电", "連": "连", "軸": "轴", "壞": "坏", "養": "养",
    "護": "护", "產": "产", "業": "业", "務": "务", "區": "区",
    "網": "网", "號": "号", "碼": "码", "馬": "马", "驅": "驱",
    "統": "统", "計": "计", "點": "点", "無": "无",
}

_SPACE_IN_CJK = re.compile(r"(?<=[\u4e00-\u9fff])[ \t]+(?=[\u4e00-\u9fff])")
_CJK_EN_BOUNDARY = re.compile(r"([\u4e00-\u9fff])\s+([A-Za-z])")
_EN_CJK_BOUNDARY = re.compile(r"([A-Za-z])\s+([\u4e00-\u9fff])")
_TRAD_RE = re.compile("[" + "".join(TRAD_TO_SIMPLE.keys()) + "]")


# ============================================================
# 层级 1：去 think
# ============================================================
def _strip_think(text: str) -> str:
    return THINK_TAG.sub("", THINK_BLOCK.sub("", text))


# ============================================================
# 层级 2：去章节标题
# ============================================================
def _strip_headings(text: str) -> str:
    if not text:
        return text
    # 去 [xxx] 或 [xxx > yyy]
    for _ in range(3):
        new = PREFIX_RE.sub("", text).strip()
        if new == text:
            break
        text = new

    out_lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        if re.match(r"^\d+\.?$", stripped) or re.match(r"^\[\d+\]$", stripped):
            continue
        hit = False
        for tw in TITLE_WORDS:
            if tw in line:
                gt_idx = line.rfind(">", 0, line.find(tw))
                if gt_idx > -1:
                    after = line[line.find(tw) + len(tw):].strip()
                    if after:
                        out_lines.append(after)
                    hit = True
                    break
        if hit:
            continue
        out_lines.append(line)
    return "\n".join(out_lines)


# ============================================================
# 层级 3：截断
# ============================================================
def _truncate_at_marker(text: str) -> str:
    earliest = len(text)
    for marker in STOP_MARKERS:
        idx = text.find(marker)
        if 0 < idx < earliest:
            earliest = idx
    return text[:earliest].rstrip()


# ============================================================
# 层级 4：繁简 + 英中
# ============================================================
def _to_simplified(text: str) -> str:
    return _TRAD_RE.sub(lambda m: TRAD_TO_SIMPLE.get(m.group(), m.group()), text)


def _normalize_text(text: str) -> str:
    if not text:
        return text
    for en, zh in TERM_MAP.items():
        text = re.sub(rf"(?<![A-Za-z]){en}(s|es)?(?![A-Za-z])", zh, text, flags=re.IGNORECASE)
    for _ in range(3):
        new = _SPACE_IN_CJK.sub("", text)
        if new == text:
            break
        text = new
    text = _CJK_EN_BOUNDARY.sub(r"\1\2", text)
    text = _EN_CJK_BOUNDARY.sub(r"\1\2", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text


# ============================================================
# 层级 5：引用去重 + 合并孤立引用 + 编号列表
# ============================================================
def _dedup_citations(text: str) -> str:
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
    text = re.sub(r"\s+([。，；：！？、])", r"\1", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def _merge_orphan_citations(text: str) -> str:
    """把只有 [数字] 的独立行合并到上一行末尾。"""
    if not text:
        return text
    lines = text.split("\n")
    out = []
    for line in lines:
        stripped = line.strip()
        m = re.match(r"^\s*(?:\d+\.\s*)?\[\s*(\d+)\s*\]\s*$", stripped)
        if m:
            cit = f"[{m.group(1)}]"
            if out:
                prev = out[-1].rstrip()
                prev = re.sub(r"[。.]\s*$", "", prev)
                out[-1] = f"{prev} {cit}。"
            continue
        out.append(line)
    return "\n".join(out)


def _format_as_numbered_list(text: str) -> str:
    """把段落格式化为编号列表。"""
    if not text:
        return text
    text = text.strip()

    # 0) 行内多编号拆行
    if "\n" not in text:
        matches = list(re.finditer(r"(?<![\d])(\d+)\.\s", text))
        if len(matches) >= 2:
            out = text
            for m in reversed(matches[1:]):
                out = out[:m.start()] + "\n" + out[m.start():]
            text = out

    # 1) 已是编号列表，规范化
    if re.match(r"^[0-9]+[\.、\)]\s", text):
        lines = []
        for line in text.splitlines():
            line = line.rstrip()
            line = re.sub(r"^(\s*)([0-9]+)[、\)]\s*", r"\1\2. ", line)
            lines.append(line)
        return "\n".join(lines)

    # 2) 按换行拆
    parts = [p.strip() for p in text.split("\n") if p.strip()]

    # 3) 分号拆
    if len(parts) <= 1:
        parts = [p.strip().rstrip("。.") for p in re.split(r"[；;]+", text) if p.strip()]

    # 4) 句号拆
    if len(parts) <= 1:
        parts = []
        for p in re.split(r"。(?!\d)", text):
            p = p.strip().rstrip("。.")
            if p:
                parts.append(p)

    if len(parts) <= 1:
        return text

    out = []
    for p in parts[:6]:
        p = re.sub(r"^\s*[0-9]+[\.、\)]\s*", "", p).strip()
        if p:
            out.append(p)
    if len(out) <= 1:
        return text
    return "\n".join(f"{i}. {p}" for i, p in enumerate(out, 1))


# ============================================================
# 主后处理链
# ============================================================
def clean_answer(text: str) -> str:
    if not text:
        return text

    text = _strip_think(text)
    text = _strip_headings(text)
    text = _truncate_at_marker(text)
    text = LEADING_NO_INFO.sub("", text)
    text = BRACKET_ACTION.sub("", text)
    text = REPEAT_CIT.sub(" ", text)
    text = re.sub(r"^\[\d+\][.、:：\s]*", "", text)
    text = re.sub(r"\n{2,}", "\n", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    text = text.strip()
    text = _dedup_citations(text)
    text = _merge_orphan_citations(text)
    text = _to_simplified(text)
    text = _normalize_text(text)
    text = _format_as_numbered_list(text)
    # 编号列表格式化后，可能又产生孤立引用（如 "1. xxx\n2. [1]"），再合并一次
    text = _merge_orphan_citations(text)
    if len(text) > 500:
        text = text[:500].rstrip()
    return text


# ============================================================
# LLM 工厂
# ============================================================
def _is_refusal(text: str) -> bool:
    if not text or len(text.strip()) < 3:
        return True
    for kw in NO_INFO_KEYWORDS:
        if kw in text:
            return True
    return False


def _is_ollama_base(base_url: str) -> bool:
    if not base_url:
        return True
    return "11434" in base_url or "ollama" in base_url.lower()


def get_llm():
    global _LLM_CACHE
    if _LLM_CACHE is not None:
        return _LLM_CACHE

    s = get_settings()
    base_url = s.llm_base_url or s.ollama_base_url
    model = s.llm_model or s.ollama_llm_model

    if _is_ollama_base(base_url):
        from langchain_ollama import ChatOllama
        _LLM_CACHE = ChatOllama(
            model=model, base_url=base_url,
            temperature=0.1, num_predict=600, num_ctx=2048,
            repeat_penalty=1.4, top_p=0.85, top_k=30,
        )
    else:
        from langchain_openai import ChatOpenAI
        _LLM_CACHE = ChatOpenAI(
            model=model, api_key=s.llm_api_key or "sk-dummy",
            base_url=base_url, temperature=0.1, timeout=30, max_tokens=400,
        )
    return _LLM_CACHE


def reset_llm_cache() -> None:
    global _LLM_CACHE
    _LLM_CACHE = None


# ============================================================
# Prompt + 生成节点
# ============================================================
PROMPT = """你是企业售后助手。根据下面的知识片段，用简洁中文回答用户问题。

【知识片段】
{context}

【用户问题】
{question}

严格按以下格式回答：

1. 第1步操作
2. 第2步操作
3. 第3步操作

规则：
- 每步一行，数字+英文句点开头（1. 2. 3.）
- 禁止输出任何章节标题（如"设备E102 报警处理"、"适用范围"、"排查步骤"、"xxx > yyy"）
- 直接说结论，不要先报章节名再给内容
- 引用编号 [1] 必须紧贴在相关句子的句号前，例如："检查温度传感器接线 [1]。"
- 引用编号绝对不能单独占一行，也不能单独作为一步
- 全部用中文简体，禁止英文单词、禁止繁体字
- 不要复述问题，不要思考过程，不要"总结/备注"
- 总字数不超过 100 字
- 如果知识片段无法回答，只回答：暂无相关依据

【回答】"""


def format_context(chunks: List[Dict], max_chunks: int = 3) -> str:
    lines = []
    for i, c in enumerate(chunks[:max_chunks], 1):
        text = c.get("text", "").strip().replace("\n", " ")
        for _ in range(3):
            new = PREFIX_RE.sub("", text).strip()
            if new == text:
                break
            text = new
        for tw in TITLE_WORDS:
            if tw in text and ">" in text:
                idx = text.find(tw)
                gt_idx = text.rfind(">", 0, idx)
                if gt_idx > -1:
                    text = text[idx + len(tw):].strip()
                    break
        lines.append(f"[{i}] {text[:180]}")
    return "\n".join(lines)


def _fallback_from_chunks(chunks: List[Dict]) -> str:
    if not chunks:
        return "暂无相关依据，建议转人工。"
    text = chunks[0].get("text", "").strip().replace("\n", " ")
    for _ in range(3):
        new = PREFIX_RE.sub("", text).strip()
        if new == text:
            break
        text = new
    return f"{text[:150].rstrip()} [1]"


def generate_node(state: AgentState) -> AgentState:
    chunks = state.get("retrieved", []) or []
    question = state.get("user_input", "")

    if not chunks or state.get("flow_status") == "rejected":
        return {
            **state,
            "answer": "抱歉，知识库中没有找到与您问题相关的内容。请补充更多信息，或回复「转人工」联系客服。",
            "citations": [],
            "flow_status": "rejected",
        }

    context = format_context(chunks, max_chunks=3)
    prompt = PROMPT.format(context=context, question=question)

    answer = ""
    try:
        resp = get_llm().invoke(prompt)
        raw = resp.content if hasattr(resp, "content") else str(resp)
        answer = clean_answer(raw)
    except Exception as e:
        answer = f"生成失败：{e}"

    if _is_refusal(answer):
        answer = clean_answer(_fallback_from_chunks(chunks))

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
