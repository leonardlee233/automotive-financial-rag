from __future__ import annotations

import csv
import json
import argparse
import sys
import os
import hashlib
import importlib.metadata
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.answering import answer_openai, format_sources, select_evidence
from src.common import ROOT, read_json, write_json, write_jsonl, sha256_file
from src.retrieval import HybridRetriever
from src.querying import rewrite_query


def summarize(rows: list[dict]) -> list[dict]:
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rewrite", action="store_true", help="Run the small rule-based query rewrite ablation")
    parser.add_argument("--baseline", action="store_true", help="Disable simple metadata-aware retrieval improvements")
    parser.add_argument("--only", default="", help="Comma-separated question ids for debugging; not a full evaluation")
    args = parser.parse_args()
    questions = read_json(ROOT / "config" / "questions.json")
    retriever = HybridRetriever()
    results = []
    out_dir = ROOT / "evaluation"
    out_dir.mkdir(exist_ok=True)
    stem = "results_semantic_baseline" if args.baseline else "results_optimized"
    if args.only:
        stem += "_debug"
    run_id = datetime.now(timezone.utc).isoformat()
    manifest = {
        'run_id': run_id,
        'index': read_json(ROOT / 'data/index/metadata.json'),
        'vectors_sha256': sha256_file(ROOT / 'data/index/vectors.npy'),
        'chunks_sha256': sha256_file(ROOT / 'data/index/chunks.jsonl'),
        'questions_sha256': sha256_file(ROOT / 'config/questions.json'),
        'source_sha256': {str(p.relative_to(ROOT)).replace('\\', '/'):sha256_file(p) for p in sorted((ROOT/'src').glob('*.py'))},
        'packages': {name:importlib.metadata.version(name) for name in ['torch','transformers','sentence-transformers','jieba','rank-bm25','numpy','pdfplumber']},
    }
    llm_file = ROOT / 'work/models/Qwen3-4B-Instruct-2507-Q4_K_M.gguf'
    if llm_file.exists():
        manifest['local_llm_sha256'] = sha256_file(llm_file)
    write_json(out_dir / f'{stem}_runtime.json', manifest)
    for item in questions:
        if args.only and item["id"] not in args.only.split(","):
            continue
        print(f"Running {item['id']}: {item['question']}", flush=True)
        retrieval_query = rewrite_query(item["question"]) if args.rewrite else item["question"]
        trace = retriever.search(retrieval_query, company=item.get("company"), top_k=8 if item["type"] == "跨公司全景" else 6, candidate_k=80, optimized=not args.baseline)
        retrieved_chunks = trace['final']
        if not args.baseline:
            trace['final'] = select_evidence(item['question'], trace['final'])
        answer = answer_openai(item["question"], trace["final"])
        evidence = "\n".join(row["text"] for row in trace["final"])
        hit_terms = [term for term in item["expected_terms"] if term in evidence]
        results.append({
            **item,
            "run_id": run_id,
            "embedding_backend": retriever.embedding_backend,
            "embedding_model": retriever.embedding_model,
            "answer_backend": os.getenv("ANSWER_BACKEND", "openai" if os.getenv("OPENAI_API_KEY") else "local"),
            "answer_model": os.getenv("OPENAI_MODEL", "gpt-5-mini") if os.getenv("OPENAI_API_KEY") else "Qwen3-4B-Instruct-2507-Q4_K_M",
            "index_sha256": manifest['chunks_sha256'],
            "vectors_sha256": manifest['vectors_sha256'],
            "answer_sha256": hashlib.sha256(answer.encode()).hexdigest(),
            "retrieval_query": trace.get("query", retrieval_query),
            "retrieval_strategy": trace.get("strategy"),
            "answer": answer,
            "llm_evidence": format_sources(trace["final"], item["question"]),
            "vector_recall": summarize(trace["vector"]),
            "bm25_recall": summarize(trace["bm25"]),
            "final_chunks": summarize(trace["final"]),
            "fused_candidates": retrieved_chunks,
            "expected_term_hits": hit_terms,
            "automatic_evidence_coverage": round(len(hit_terms) / max(1, len(item["expected_terms"])), 2),
            "manual_verdict": item.get("manual_verdict", "pending"),
            "error_type": item.get("error_type", "待人工核验"),
            "reason": item.get("reason", "评测运行后结合原始页码核验。"),
        })
        write_jsonl(out_dir / f"{stem}.jsonl", results)
        print(f"Saved {item['id']}", flush=True)
    out_dir = ROOT / "evaluation"
    out_dir.mkdir(exist_ok=True)
    write_jsonl(out_dir / f"{stem}.jsonl", results)
    with (out_dir / f"{stem}.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        fields = ["id", "type", "company", "question", "automatic_evidence_coverage", "manual_verdict", "error_type", "reason", "answer"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in results:
            writer.writerow({key: row.get(key) for key in fields})
    lines = ["# 10道问题真实运行结果", "", "完整召回轨迹见 `results.jsonl`。", ""]
    for row in results:
        final_ids = ", ".join(item["chunk_id"] for item in row["final_chunks"])
        lines.extend([
            f"## {row['id']}｜{row['type']}｜{row['manual_verdict']}", "",
            f"**问题：** {row['question']}", "",
            f"**最终块：** {final_ids}", "",
            f"**证据覆盖：** {row['automatic_evidence_coverage']:.0%}", "",
            f"**错误类型：** {row['error_type']}", "",
            f"**核验说明：** {row['reason']}", "",
            "**回答：**", "", row["answer"], "",
        ])
    (out_dir / f"{stem}.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {stem} evaluation artifacts for {len(results)} questions.")


if __name__ == "__main__":
    main()

