"""Actually run the two panoramic questions with traceable hybrid retrieval."""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import ROOT, read_json, read_jsonl, write_jsonl
from src.retrieval import HybridRetriever
from src.panorama import summarize_financials, summarize_risks


def main():
    questions = read_json(ROOT / "config/questions.json")[-2:]
    rows = read_jsonl(ROOT / "evaluation/results_optimized.jsonl")
    assert [r["id"] for r in rows] == [f"Q{i:02d}" for i in range(1, 11)]
    retriever = HybridRetriever()
    companies = sorted({r["company"] for r in retriever.chunks})
    run_id = datetime.now(timezone.utc).isoformat()
    runtime = read_json(ROOT / "evaluation/results_optimized_runtime.json")
    new_rows = []
    for item in questions:
        print(f"Retrieving {item['id']}", flush=True)
        trace = retriever.search(item["question"], top_k=8, candidate_k=80, optimized=True)
        if item["id"] == "Q09":
            answer, evidence, detail = summarize_financials(retriever.chunks, companies)
            backend = "structured_financial_table_aggregation"
        else:
            answer, evidence, detail = summarize_risks(trace["final"], companies)
            backend = "source_line_risk_grouping"
        evidence = [{**chunk, "rank": rank} for rank, chunk in enumerate(evidence, 1)]
        evidence_text = "\n\n".join(f"[{e['company']} PDF第{e['page']}页 {e['chunk_id']}]\n{e['text']}" for e in evidence)
        hits = [term for term in item["expected_terms"] if term in evidence_text]
        row = {**item, "run_id": run_id, "embedding_backend": retriever.embedding_backend,
               "embedding_model": retriever.embedding_model, "answer_backend": backend,
               "answer_model": "none (deterministic aggregation)",
               "index_sha256": runtime["chunks_sha256"], "vectors_sha256": runtime["vectors_sha256"],
               "answer_sha256": hashlib.sha256(answer.encode()).hexdigest(), "retrieval_query": trace["query"],
               "retrieval_strategy": trace["strategy"] + "; source-grounded panoramic aggregation",
               "answer": answer, "llm_evidence": evidence_text, "vector_recall": trace["vector"],
               "bm25_recall": trace["bm25"], "fused_candidates": trace["final"],
               "final_chunks": evidence, "aggregation_detail": detail,
               "expected_term_hits": hits, "automatic_evidence_coverage": round(len(hits) / max(1, len(item["expected_terms"])), 2),
               "manual_verdict": "pending", "error_type": "待复核", "reason": "待逐页核验"}
        new_rows.append(row)
        print(f"Saved {item['id']}: {len(evidence)} source chunks", flush=True)
    write_jsonl(ROOT / "evaluation/results_optimized.jsonl", rows[:8] + new_rows)
    print("Panoramic results written.")


if __name__ == "__main__":
    main()
