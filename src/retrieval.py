from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import jieba
import numpy as np
from rank_bm25 import BM25Okapi

from .common import ROOT, read_json, read_jsonl
from .embeddings import embed_texts
from .querying import rewrite_query


def tokenize(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text.lower())
    return [token for token in jieba.lcut(normalized) if token.strip()]


class HybridRetriever:
    def __init__(self, index_dir: Path | None = None):
        self.index_dir = index_dir or ROOT / "data" / "index"
        metadata = read_json(self.index_dir / "metadata.json")
        self.embedding_backend = metadata["embedding_backend"]
        self.embedding_model = metadata["embedding_model"]
        self.chunks = read_jsonl(self.index_dir / "chunks.jsonl")
        self.vectors = np.load(self.index_dir / "vectors.npy")
        tokenized = json.loads((self.index_dir / "bm25_tokens.json").read_text(encoding="utf-8"))
        self.bm25 = BM25Okapi(tokenized)

    def _filtered_indices(self, company: str | None) -> np.ndarray:
        if not company or company == "全部公司":
            return np.arange(len(self.chunks))
        return np.array([i for i, chunk in enumerate(self.chunks) if chunk["company"] == company])

    def search(
        self,
        query: str,
        company: str | None = None,
        top_k: int = 6,
        candidate_k: int = 30,
        rrf_k: int = 60,
        optimized: bool = True,
    ) -> dict[str, Any]:
        original_query = query
        companies = sorted({row["company"] for row in self.chunks})
        if optimized and not company:
            mentioned = [name for name in companies if name in query]
            if len(mentioned) == 1:
                company = mentioned[0]
            elif any(word in query for word in ("10家公司", "十家公司", "这些公司", "所有公司")):
                traces = [self.search(query, name, top_k=3, candidate_k=candidate_k, optimized=True) for name in companies]
                result = {key: [row for trace in traces for row in trace[key]] for key in ("vector", "bm25", "final")}
                result["query"] = rewrite_query(query)
                result["strategy"] = "company-stratified: 3 chunks per company"
                return result
        if optimized:
            query = rewrite_query(query)
        allowed = self._filtered_indices(company)
        if optimized:
            if '管理层' in original_query and '风险' in original_query:
                management = np.array([i for i in allowed if '管理层' in self.chunks[i]['section']])
                if len(management):
                    allowed = management
            # Negative instructions mentioning the other scope must not win lexical search.
            positive = re.split(r"不要|请勿|别拿|而非", original_query)[0]
            scope = "母公司" if "母公司" in positive else "合并" if "合并" in positive else None
            if scope:
                opposite = "合并" if scope == "母公司" else "母公司"
                allowed = np.array([i for i in allowed if self.chunks[i].get("statement_scope") != opposite])
        if not len(allowed):
            return {"vector": [], "bm25": [], "final": []}
        query_vector, _ = embed_texts([query], self.embedding_backend.split(":")[0], self.embedding_model, query=True)
        vector_scores = self.vectors[allowed] @ query_vector[0]
        vector_order = allowed[np.argsort(-vector_scores)[:candidate_k]]
        vector_rows = [
            {"rank": rank, "score": float(self.vectors[idx] @ query_vector[0]), **self.chunks[idx]}
            for rank, idx in enumerate(vector_order, 1)
        ]

        all_bm25_scores = np.asarray(self.bm25.get_scores(tokenize(query)))
        bm25_order = allowed[np.argsort(-all_bm25_scores[allowed])[:candidate_k]]
        bm25_rows = [
            {"rank": rank, "score": float(all_bm25_scores[idx]), **self.chunks[idx]}
            for rank, idx in enumerate(bm25_order, 1)
        ]

        fused: dict[str, float] = defaultdict(float)
        chunk_by_id: dict[str, dict[str, Any]] = {}
        for rows in (vector_rows, bm25_rows):
            for row in rows:
                cid = row["chunk_id"]
                fused[cid] += 1.0 / (rrf_k + row["rank"])
                chunk_by_id[cid] = {k: v for k, v in row.items() if k not in {"rank", "score"}}
        raw_fused = dict(fused)
        if optimized:
            for cid, chunk in chunk_by_id.items():
                content = chunk["text"]
                factor = 1.0
                if any(t in query for t in ("营业收入", "净利润", "现金流")) and "研发" not in query and "未分配利润" not in query:
                    if "主要会计数据" in content or "主要财务指标" in content:
                        factor *= 1.8
                if "研发" in query and "研发" in content:
                    factor *= 1.35
                    if "占" in content and ("比例" in content or "%" in content):
                        factor *= 1.15
                if "合并利润表" in original_query and chunk.get("table_name") and "合并利润表" in chunk["table_name"]:
                    factor *= 2
                if "母公司" in original_query and "未分配利润" in query and "母公司" in content and "未分配利润" in content:
                    factor *= 1.5
                if "风险" in query and "风险" in content and ("管理层" in chunk["section"] or "可能面对的风险" in content):
                    factor *= 1.5
                    if any(t in content for t in ('可能面对的风险','面临的风险和应对','可能面临的风险')):
                        factor *= 1.8
                fused[cid] *= factor
        # Prefer distinct evidence over near-identical text/table duplicates.
        final_ids = []
        signatures = []
        for cid in sorted(fused, key=fused.get, reverse=True):
            chunk = chunk_by_id[cid]
            signature = set(re.findall(r"[\u4e00-\u9fff]{2,}|[\d,.]+", chunk["text"]))
            if any(len(signature & other) / max(1, len(signature | other)) > 0.85 for other in signatures):
                continue
            final_ids.append(cid)
            signatures.append(signature)
            if len(final_ids) >= top_k:
                break
        final_rows = [
            {"rank": rank, "rrf_score": raw_fused[cid], "selection_score": fused[cid],
             "boost_factor": fused[cid] / raw_fused[cid], **chunk_by_id[cid]}
            for rank, cid in enumerate(final_ids, 1)
        ]
        return {"vector": vector_rows, "bm25": bm25_rows, "final": final_rows,
                "query": query, "strategy": "metadata-aware RRF" if optimized else "plain RRF"}

