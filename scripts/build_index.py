from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import hashlib
from pathlib import Path

import jieba
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import ROOT, read_jsonl, write_json, write_jsonl
from src.embeddings import embed_texts
from src.retrieval import tokenize


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=["qwen", "semantic", "hash"], default="qwen")
    parser.add_argument("--model", default=os.getenv("EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-0.6B"))
    args = parser.parse_args()
    chunks = read_jsonl(ROOT / "data" / "processed" / "chunks.jsonl")
    if not chunks:
        raise SystemExit("No chunks. Run parse_reports.py first.")
    texts = [chunk["embedding_text"] for chunk in chunks]
    cache_key = hashlib.sha256((args.model + args.backend + "window-mean-v3" + "".join(texts)).encode()).hexdigest()[:16]
    cache_dir = ROOT / "work" / "embedding_batches" / cache_key
    cache_dir.mkdir(parents=True, exist_ok=True)
    batches = []
    model_used = args.model
    for start in range(0, len(texts), 32):
        path = cache_dir / f"{start:06d}.npy"
        if path.exists():
            batch = np.load(path)
        else:
            batch, model_used = embed_texts(texts[start:start + 32], args.backend, args.model)
            np.save(path, batch)
        batches.append(batch)
        print(f"Embedded {min(start + 32, len(texts))}/{len(texts)}", flush=True)
    vectors = np.concatenate(batches)
    index_dir = ROOT / "data" / "index"
    index_dir.mkdir(parents=True, exist_ok=True)
    np.save(index_dir / "vectors.npy", vectors)
    write_jsonl(index_dir / "chunks.jsonl", chunks)
    tokens = [tokenize(text) for text in texts]
    (index_dir / "bm25_tokens.json").write_text(json.dumps(tokens, ensure_ascii=False), encoding="utf-8")
    write_json(index_dir / "metadata.json", {
        "embedding_backend": args.backend,
        "embedding_model": model_used,
        "embedding_text_prefix": "公司名 + 章节名",
        "chunk_count": len(chunks),
        "vector_dimensions": int(vectors.shape[1]),
        "bm25_tokenizer": "jieba",
        "fusion": "RRF(k=60)",
        "embedding_windowing": "BGE: company+section repeated, 360 chars/40 overlap, normalized mean; Qwen: full chunk",
        "precision": "float32",
    })
    print(f"Built hybrid index: {len(chunks)} chunks, {vectors.shape[1]} dimensions, backend={model_used}")


if __name__ == "__main__":
    main()

