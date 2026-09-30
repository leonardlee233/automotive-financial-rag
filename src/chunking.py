from __future__ import annotations

import re
from typing import Iterable

SENTENCE_END = re.compile(r"[。！？；!?;\n]")


def _best_cut(text: str, start: int, target: int, lower_bound: int) -> int:
    end = min(len(text), target)
    if end == len(text):
        return end
    floor = max(start + lower_bound, end - 120)
    for position in range(end - 1, floor - 1, -1):
        if SENTENCE_END.match(text[position]):
            return position + 1
    return end


def chunk_text(text: str, size: int = 800, overlap: int = 120) -> Iterable[str]:
    """Split Chinese text near sentence boundaries with deterministic overlap."""
    text = text.strip()
    if not text:
        return
    start = 0
    while start < len(text):
        end = _best_cut(text, start, start + size, max(240, size // 2))
        chunk = text[start:end].strip()
        if chunk:
            yield chunk
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)

