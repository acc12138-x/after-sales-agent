"""自研 RAG 评估器（不依赖 ragas）。

4 个指标：
- faithfulness      答案是否基于 contexts（0-1）
- answer_relevancy  答案是否切题（0-1）
- context_precision 检索的 contexts 有多少相关（0-1）
- context_recall    ground_truth 能否从 contexts 推导（0-1）

每个指标都用 LLM-as-judge：给 LLM 打分模板 → 解析 0-1 分数。
"""
from __future__ import annotations
import re
from typing import Dict, List

from app.workflows.nodes.generate import get_llm


# ============================================================
# Judge LLM 调用
# ============================================================
def _ask_judge(prompt: str, max_retry: int = 2) -> str:
    llm = get_llm()
    for _ in range(max_retry):
        try:
            resp = llm.invoke(prompt)
            text = resp.content if hasattr(resp, "content") else str(resp)
            return text.strip()
        except Exception:
            continue
    return ""


def _parse_score(text: str, default: float = 0.0) -> float:
    """从 LLM 输出里解析 0-1 之间的分数。"""
    if not text:
        return default
    # 找 "分数：0.8" / "score: 0.8" / "0.8" 等
    m = re.search(r"(?:分数|score|评分)[\s:：]*([0-9]*\.?[0-9]+)", text, re.IGNORECASE)
    if not m:
        m = re.search(r"\b([0-9]*\.?[0-9]+)\b", text)
    if not m:
        return default
    try:
        v = float(m.group(1))
        # 兼容 0-10 分制
        if v > 1.0:
            v = v / 10.0
        return max(0.0, min(1.0, v))
    except Exception:
        return default


# ============================================================
# 指标 1: Faithfulness
# ============================================================
FAITHFUL_PROMPT = """你是评估员。判断【答案】是否完全基于【参考资料】中的信息。

评估规则：
- 如果答案的所有事实性内容都能在参考资料中找到依据 -> 1.0
- 如果答案有编造、曲解、添加参考资料没有的信息 -> 按比例扣分
- 如果答案回答"暂无相关依据" -> 0.5（合理拒答）
- 如果答案为对话内容（如"已创建工单"）不涉及事实引用 -> 1.0

【参考资料】
{contexts}

【问题】
{question}

【答案】
{answer}

只回复一个 0.0-1.0 之间的分数，格式：分数：X.X"""


def score_faithfulness(question: str, answer: str, contexts: List[str]) -> float:
    ctx = "\n\n".join(contexts[:3]) if contexts else "（无检索结果）"
    prompt = FAITHFUL_PROMPT.format(contexts=ctx, question=question, answer=answer)
    return _parse_score(_ask_judge(prompt), default=0.5)


# ============================================================
# 指标 2: Answer Relevancy
# ============================================================
RELEVANCY_PROMPT = """你是评估员。判断【答案】是否直接回答了【问题】。

评估规则：
- 1.0 = 答案直接切题，包含问题所问的关键信息
- 0.5 = 部分切题，答非所问一半
- 0.0 = 完全跑题，或答非所问
- 合理的拒答（如知识库无相关信息）-> 0.7
- 建单成功等业务动作 -> 1.0

【问题】
{question}

【答案】
{answer}

只回复一个 0.0-1.0 之间的分数，格式：分数：X.X"""


def score_answer_relevancy(question: str, answer: str) -> float:
    prompt = RELEVANCY_PROMPT.format(question=question, answer=answer)
    return _parse_score(_ask_judge(prompt), default=0.5)


# ============================================================
# 指标 3: Context Precision
# ============================================================
PRECISION_PROMPT = """你是评估员。判断【参考资料片段】是否与【问题】相关。

评估规则：
- 1.0 = 该片段包含回答问题的关键信息
- 0.5 = 部分相关，有间接关联
- 0.0 = 完全无关

【问题】
{question}

【片段】
{chunk}

只回复一个 0.0-1.0 之间的分数，格式：分数：X.X"""


def score_context_precision(question: str, contexts: List[str]) -> float:
    if not contexts:
        return 0.0
    scores = []
    for c in contexts[:3]:
        prompt = PRECISION_PROMPT.format(question=question, chunk=c[:500])
        scores.append(_parse_score(_ask_judge(prompt), default=0.0))
    return sum(scores) / len(scores) if scores else 0.0


# ============================================================
# 指标 4: Context Recall
# ============================================================
RECALL_PROMPT = """你是评估员。判断【参考答案】能否从【参考资料】中推导出来。

评估规则：
- 1.0 = 参考答案的关键信息都能在参考资料里找到
- 0.5 = 部分能推导
- 0.0 = 参考资料完全没有相关信息

【参考资料】
{contexts}

【参考答案】
{ground_truth}

只回复一个 0.0-1.0 之间的分数，格式：分数：X.X"""


def score_context_recall(contexts: List[str], ground_truth: str) -> float:
    if not contexts:
        return 0.0
    ctx = "\n\n".join(contexts[:3])
    prompt = RECALL_PROMPT.format(contexts=ctx, ground_truth=ground_truth)
    return _parse_score(_ask_judge(prompt), default=0.0)


# ============================================================
# 评估主流程
# ============================================================
def evaluate_one(question: str, answer: str, contexts: List[str], ground_truth: str) -> Dict[str, float]:
    return {
        "faithfulness":      score_faithfulness(question, answer, contexts),
        "answer_relevancy":  score_answer_relevancy(question, answer),
        "context_precision": score_context_precision(question, contexts),
        "context_recall":    score_context_recall(contexts, ground_truth),
    }
