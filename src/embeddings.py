from __future__ import annotations

import hashlib
import math
import os
from functools import lru_cache
from pathlib import Path
from collections.abc import Iterable

import numpy as np


def _hash_index(token: str, dimensions: int) -> tuple[int, float]:
    raw = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    value = int.from_bytes(raw, "little")
    return value % dimensions, -1.0 if value & 1 else 1.0


def hash_char_ngram_embeddings(texts: Iterable[str], dimensions: int = 1536) -> np.ndarray:
    """Offline semantic-ish baseline used only when Qwen cannot be run locally."""
    rows = []
    for text in texts:
        compact = "".join(text.lower().split())
        vector = np.zeros(dimensions, dtype=np.float32)
        for n in (1, 2, 3):
            for i in range(max(0, len(compact) - n + 1)):
                token = compact[i : i + n]
                index, sign = _hash_index(token, dimensions)
                vector[index] += sign / math.sqrt(n)
        norm = float(np.linalg.norm(vector))
        if norm:
            vector /= norm
        rows.append(vector)
    return np.stack(rows) if rows else np.empty((0, dimensions), dtype=np.float32)


@lru_cache(maxsize=1)
def load_embedding_model(model_name: str):
    import torch
    from sentence_transformers import SentenceTransformer
    torch.set_num_threads(min(4, os.cpu_count() or 4))
    local = Path(__file__).resolve().parents[1] / "work/models" / model_name.split("/")[-1]
    source = str(local) if (local / "model.safetensors").exists() else model_name
    # This CPU lacks native BF16 instructions: force FP32 instead of very slow BF16 emulation.
    model = SentenceTransformer(source, cache_folder=os.getenv("HF_HOME", "work/models"),
                                model_kwargs={"dtype": torch.float32})
    model.max_seq_length = 512 if "bge" in model_name.lower() else 2048
    return model


def embed_texts(texts: list[str], backend: str, model_name: str, *, query: bool = False) -> tuple[np.ndarray, str]:
    if backend == "hash":
        return hash_char_ngram_embeddings(texts), "hash-char-ngram-1536"
    if backend not in {"qwen", "semantic"}:
        raise ValueError(f"Unknown embedding backend: {backend}")
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError(
            "Qwen mode requires sentence-transformers and torch. "
            "Install the optional packages listed in requirements.txt."
        ) from exc
    model = load_embedding_model(model_name)
    if "bge" in model_name.lower() and not query:
        # Preserve the complete 800-character chunk despite BGE's 512-token limit.
        # Each window repeats company/section; store one normalized mean vector per chunk.
        from .chunking import chunk_text
        windows, owners = [], []
        for index, text in enumerate(texts):
            parts = text.split("\n", 2)
            prefix = "\n".join(parts[:2]) + "\n" if len(parts) == 3 else ""
            body = parts[2] if len(parts) == 3 else text
            for piece in chunk_text(body, size=360, overlap=40):
                windows.append(prefix + piece)
                owners.append(index)
        encoded = model.encode(windows, batch_size=16, show_progress_bar=False,
                               normalize_embeddings=True, convert_to_numpy=True, prompt="")
        vectors = np.zeros((len(texts), encoded.shape[1]), dtype=np.float32)
        for owner, vector in zip(owners, encoded):
            vectors[owner] += vector
        vectors /= np.maximum(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-12)
        return vectors, model_name
    vectors = model.encode(
        texts,
        batch_size=int(os.getenv("EMBEDDING_BATCH_SIZE", "4")),
        prompt=(("为这个句子生成表示以用于检索相关文章：" if "bge" in model_name.lower() else "Instruct: Retrieve financial report passages that answer the question.\nQuery: ") if query else ""),
        show_progress_bar=True,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    return np.asarray(vectors, dtype=np.float32), model_name

