
"""父子块切片：子块检索，父块生成。"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Dict, List


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


def _split_by_headings(text: str) -> List[tuple]:
    lines = text.splitlines()
    sections = []
    current_heading = ""
    buffer: List[str] = []

    heading_re = re.compile(r"^(#{1,6})\s+(.*)$")

    for line in lines:
        m = heading_re.match(line)
        if m:
            if buffer:
                sections.append((current_heading, "\n".join(buffer).strip()))
                buffer = []
            current_heading = m.group(2).strip()
        else:
            buffer.append(line)
    if buffer:
        sections.append((current_heading, "\n".join(buffer).strip()))
    return sections


def _split_long_text(text: str, chunk_size: int, overlap: int) -> List[str]:
    if len(text) <= chunk_size:
        return [text]
    out = []
    start = 0
    step = max(1, chunk_size - overlap)
    while start < len(text):
        out.append(text[start:start + chunk_size])
        start += step
    return out


def chunk_document(
    text: str,
    doc_id: str,
    source: str = "",
    chunk_size: int = 512,
    chunk_overlap: int = 64,
    extra_metadata: Dict | None = None,
) -> List[Chunk]:
    extra_metadata = extra_metadata or {}
    sections = _split_by_headings(text)
    if not sections:
        sections = [("", text)]

    all_chunks: List[Chunk] = []

    for idx, (heading, body) in enumerate(sections):
        if not body.strip():
            continue

        parent_text = f"# {heading}\n\n{body}" if heading else body
        parent_id = _make_id(f"{doc_id}-p{idx}", parent_text)

        all_chunks.append(Chunk(
            chunk_id=parent_id,
            text=parent_text,
            parent_id=parent_id,
            is_parent=True,
            metadata={
                "doc_id": doc_id,
                "source": source,
                "heading": heading,
                "section_index": idx,
                "type": "parent",
                **extra_metadata,
            },
        ))

        for sub_idx, sub_text in enumerate(
            _split_long_text(body, chunk_size, chunk_overlap)
        ):
            sub_text = sub_text.strip()
            if not sub_text:
                continue
            child_id = _make_id(f"{parent_id}-c{sub_idx}", sub_text)
            all_chunks.append(Chunk(
                chunk_id=child_id,
                text=sub_text,
                parent_id=parent_id,
                is_parent=False,
                metadata={
                    "doc_id": doc_id,
                    "source": source,
                    "heading": heading,
                    "section_index": idx,
                    "sub_index": sub_idx,
                    "type": "child",
                    **extra_metadata,
                },
            ))

    return all_chunks
