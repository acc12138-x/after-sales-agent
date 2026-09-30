"""父子块切片（生产级）。

设计参考：
- LangChain RecursiveCharacterTextSplitter（递归分隔符）
- MarkdownHeaderTextSplitter（标题路径）
- Anthropic Contextual Retrieval（上下文前置）

核心规则：
1. 按 Markdown 标题（# ## ###）拆父块，保留 heading_path
2. 每个父块内按递归分隔符（段落 > 换行 > 句子 > 逗号）拆子块
3. 子块之间句级 overlap（默认 20%）
4. 子块文本前拼接 heading_path，让检索时能看到层级
5. 表格 / 代码块整段保留，不切开
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Dict, List, Tuple


# ---------- 递归分隔符（从粗到细）----------
SEPARATORS = [
    "\n\n",      # 段落
    "\n",         # 换行
    "。", "！", "？", "；",     # 中文句子结束
    ". ", "! ", "? ", "; ",   # 英文句子结束
    "，", ",",     # 逗号
    " ",           # 空格
    "",            # 字符级兜底
]

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
TABLE_LINE_RE = re.compile(r"^\s*\|.*\|\s*$")
CODE_FENCE_RE = re.compile(r"^\s*```")


@dataclass
class Chunk:
    chunk_id: str
    text: str
    parent_id: str
    is_parent: bool
    metadata: Dict = field(default_factory=dict)


def _make_id(prefix: str, content: str) -> str:
    h = hashlib.md5(content.encode("utf-8")).hexdigest()[:10]
    return f"{prefix}-{h}"


def _split_by_headings(text: str) -> List[Tuple[str, str]]:
    """按 Markdown 标题切分，返回 [(heading_path, body), ...]。

    heading_path 形如："设备 E102 > 排查步骤"
    """
    lines = text.split("\n")
    sections: List[Tuple[str, str]] = []
    heading_stack: Dict[int, str] = {}     # level -> title
    current_body: List[str] = []

    def _flush():
        if current_body:
            body = "\n".join(current_body).strip()
            path = " > ".join(
                heading_stack[k] for k in sorted(heading_stack) if heading_stack[k]
            )
            if body or path:
                sections.append((path, body))
        current_body.clear()

    in_code = False
    for line in lines:
        if CODE_FENCE_RE.match(line):
            in_code = not in_code
            current_body.append(line)
            continue

        m = HEADING_RE.match(line) if not in_code else None
        if m:
            _flush()
            level = len(m.group(1))
            title = m.group(2).strip()
            # 清掉更深的层级
            for k in list(heading_stack.keys()):
                if k >= level:
                    del heading_stack[k]
            heading_stack[level] = title
        else:
            current_body.append(line)

    _flush()
    return sections or [("", text)]


def _split_sentences(text: str) -> List[str]:
    """按句子切分（保护表格和代码块）。"""
    out: List[str] = []
    buf: List[str] = []
    in_code = False

    for line in text.split("\n"):
        # 代码块整体作为一个"句子"
        if CODE_FENCE_RE.match(line):
            in_code = not in_code
            buf.append(line)
            if not in_code:
                out.append("\n".join(buf))
                buf = []
            continue

        if in_code:
            buf.append(line)
            continue

        # 表格行整体保留
        if TABLE_LINE_RE.match(line):
            buf.append(line)
            continue

        # 普通文本按标点切句
        for s in re.split(r"(?<=[。！？；!?;])\s*", line):
            if s.strip():
                buf.append(s)

    if buf:
        out.append("\n".join(buf))
    return out


def _recursive_split(text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
    """句子级切分 + 句子级 overlap。

    1. 先按句子切
    2. 累积到接近 chunk_size 时输出
    3. 下一块开头 = 上一块尾部若干句（overlap）
    """
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    sentences = _split_sentences(text)
    if not sentences:
        return [text]

    chunks: List[str] = []
    cur: List[str] = []
    cur_len = 0

    for s in sentences:
        s_len = len(s)
        if cur_len + s_len <= chunk_size:
            cur.append(s)
            cur_len += s_len
        else:
            if cur:
                chunks.append("".join(cur))

            # overlap：从上一块尾部取若干句（按字数近似）
            overlap_sents: List[str] = []
            acc = 0
            for prev in reversed(cur):
                if acc + len(prev) > chunk_overlap:
                    break
                overlap_sents.insert(0, prev)
                acc += len(prev)
            cur = overlap_sents + [s]
            cur_len = sum(len(x) for x in cur)

    if cur:
        chunks.append("".join(cur))

    # 单句超长 -> 字符级兜底切
    result: List[str] = []
    for c in chunks:
        if len(c) <= chunk_size * 1.5:
            result.append(c)
        else:
            step = max(1, chunk_size - chunk_overlap)
            for i in range(0, len(c), step):
                result.append(c[i:i + chunk_size])
    return [c for c in result if c.strip()]


def chunk_document(
    text: str,
    doc_id: str,
    source: str = "",
    chunk_size: int = 512,
    chunk_overlap: int = 64,
    extra_metadata: Dict | None = None,
) -> List[Chunk]:
    """主入口：产出 [父块, 子块, 父块, 子块, ...]。

    - 父块：完整 section（含 heading），用于生成阶段
    - 子块：section 内的小块，前面拼接 heading_path，用于检索
    """
    extra_metadata = extra_metadata or {}
    sections = _split_by_headings(text)

    all_chunks: List[Chunk] = []

    for idx, (heading_path, body) in enumerate(sections):
        if not body.strip():
            continue

        # ---------- 父块 ----------
        parent_text = f"{heading_path}\n\n{body}" if heading_path else body
        parent_id = _make_id(f"{doc_id}-p{idx}", parent_text)

        all_chunks.append(Chunk(
            chunk_id=parent_id,
            text=parent_text,
            parent_id=parent_id,
            is_parent=True,
            metadata={
                "doc_id": doc_id,
                "source": source,
                "heading_path": heading_path,
                "section_title": heading_path.split(" > ")[-1] if heading_path else "",
                "section_index": idx,
                "type": "parent",
                **extra_metadata,
            },
        ))

        # ---------- 子块 ----------
        sub_texts = _recursive_split(body, chunk_size, chunk_overlap)
        for sub_idx, sub_text in enumerate(sub_texts):
            sub_text = sub_text.strip()
            if not sub_text:
                continue

            # 子块前面拼 heading_path，让检索时能看到层级
            contextual_text = (
                f"[{heading_path}]\n{sub_text}" if heading_path else sub_text
            )
            child_id = _make_id(f"{parent_id}-c{sub_idx}", contextual_text)

            all_chunks.append(Chunk(
                chunk_id=child_id,
                text=contextual_text,
                parent_id=parent_id,
                is_parent=False,
                metadata={
                    "doc_id": doc_id,
                    "source": source,
                    "heading_path": heading_path,
                    "section_title": heading_path.split(" > ")[-1] if heading_path else "",
                    "section_index": idx,
                    "sub_index": sub_idx,
                    "type": "child",
                    "parent_id": parent_id,
                    **extra_metadata,
                },
            ))

    return all_chunks
