"""Separate source retrieval coverage from answer quality for the ten fixed questions."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import ROOT, read_json, read_jsonl


STAGES = ("vector_recall", "bm25_recall", "fused_candidates", "final_chunks")


def matches(chunk: dict, expected: dict) -> bool:
    if chunk.get("company") != expected["company"]:
        return False
    if "page" in expected and chunk.get("page") != expected["page"]:
        return False
    if expected.get("table_name_contains") not in (None, "") and expected["table_name_contains"] not in (chunk.get("table_name") or ""):
        return False
    if expected.get("scope") and chunk.get("statement_scope") != expected["scope"]:
        return False
    if expected.get("section_contains") and expected["section_contains"] not in chunk.get("section", ""):
        return False
    if expected.get("text_contains") and expected["text_contains"] not in chunk.get("text", ""):
        return False
    return True


def main() -> None:
    reference = read_json(ROOT / "evaluation/reference_sources.json")
    results = read_jsonl(ROOT / "evaluation/results_optimized.jsonl")
    assert len(results) == len(reference) == 10
    records = []
    for row in results:
        expected = reference[row["id"]]
        stages = {}
        for stage in STAGES:
            chunks = row[stage]
            hits = [entry for entry in expected if any(matches(chunk, entry) for chunk in chunks)]
            stages[stage] = {"hits": len(hits), "total": len(expected),
                             "missing_companies": [entry["company"] for entry in expected if entry not in hits]}
        records.append({"id": row["id"], "type": row["type"], "question": row["question"],
                        "source_requirement": expected, "stages": stages,
                        "ai_answer_verdict": row["manual_verdict"], "answer_error_type": row["error_type"],
                        "independent_human_review": "not_done"})
    (ROOT / "evaluation/retrieval_audit.json").write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# 召回与答案分开评价", "",
             "来源目标由 `reference_sources.json` 固定；Q01–Q08按公司、原页和必要口径核对，Q09按10家公司主要会计数据表逐项核对，Q10按10家公司管理层风险段落核对。",
             "Vector/BM25 为候选池命中，不代表答案正确；Q09 的最终证据含按公司补查的表格行，不能冒称全部来自融合 Top-K。", "",
             "| 题号 | Vector候选 | BM25候选 | 融合候选 | 最终证据 | AI辅助答案判定 |",
             "|---|---:|---:|---:|---:|---|"]
    for record in records:
        cells = [f"{record['stages'][stage]['hits']}/{record['stages'][stage]['total']}" for stage in STAGES]
        lines.append(f"| {record['id']} | {' | '.join(cells)} | {record['ai_answer_verdict']} |")
    lines.extend(["", "判定示例：Q05 来源页命中，但答案把14.40%误写成14.40成；Q09 最终证据覆盖10家公司，仍缺经营差异的原文解释；Q10 覆盖10家公司，但风险分类有边界。",
                  "", "以上答案判定由 AI 助手辅助复核，独立人工核验尚未完成（0/10）。", ""])
    (ROOT / "evaluation/retrieval_audit.md").write_text("\n".join(lines), encoding="utf-8")
    print("Audited retrieval and answers separately for", len(records), "questions")
    print("Final source coverage:", [(r["id"], r["stages"]["final_chunks"]["hits"], r["stages"]["final_chunks"]["total"]) for r in records])


if __name__ == "__main__":
    main()
