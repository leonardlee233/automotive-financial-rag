"""Render the reviewed JSONL into readable deliverables, without changing scores."""
import csv
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import ROOT, read_jsonl, read_json


def main():
    rows = read_jsonl(ROOT / "evaluation/results_optimized.jsonl")
    audits = {r["id"]: r for r in read_json(ROOT / "evaluation/retrieval_audit.json")}
    counts = Counter(r["ai_verdict"] for r in rows)
    lines = ["# 财报问答：10道原题实际结果", "",
             f"AI辅助判定：完全正确 {counts['correct']}/10；部分正确 {counts['partial']}；错误 {counts['wrong']}。partial 不计入正确率。独立人工核验：0/10，尚未进行。", "",
             "先核对报告、表格口径、单位和原页。召回来源命中与答案正确分开记录；候选命中不等于模型答对。该题集用于优化，不是未知题的泛化测试。", ""]
    for row in rows:
        audit = audits[row["id"]]["stages"]
        final = audit["final_chunks"]
        fused = audit["fused_candidates"]
        lines.extend([f"## {row['id']} · {row['type']} · AI判定：{row['ai_verdict']}", "",
                      row["question"], "", row["answer"], "", "### 核验", "", row["reason"], "",
                      f"错误类型：{row['error_type']}", "",
                      f"来源召回：融合候选 {fused['hits']}/{fused['total']}，最终证据 {final['hits']}/{final['total']}；独立人工核验未完成。", "",
                      "### 最终证据块", ""])
        for chunk in row["final_chunks"]:
            lines.append(f"- {chunk['chunk_id']}｜{chunk['company']}｜PDF第{chunk['page']}页｜{chunk.get('table_name') or chunk['section']}")
        lines.extend(["", "完整 Vector/BM25 候选、最终证据全文、模型配置和哈希见同名 JSONL。", ""])
    (ROOT / "evaluation/results_optimized.md").write_text("\n".join(lines), encoding="utf-8")
    with (ROOT / "evaluation/results_optimized.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        fields = ["id", "type", "question", "answer", "ai_verdict", "independent_human_review", "fused_source_hits", "final_source_hits", "error_type", "reason"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            record = {key: row[key] for key in fields if key in row}
            record["fused_source_hits"] = audits[row["id"]]["stages"]["fused_candidates"]["hits"]
            record["final_source_hits"] = audits[row["id"]]["stages"]["final_chunks"]["hits"]
            writer.writerow(record)
    notes = read_json(ROOT / "evaluation/conclusion_notes.json")
    submission_config = ROOT / "config/submission.json"
    repository_url = read_json(submission_config).get("repository_url", "").strip() if submission_config.exists() else ""
    if not repository_url:
        repository_url = "[待填写：上传代码后的真实 GitHub 或 cnb.cool 仓库 URL]"
    conclusion = ["# 汽车零部件财报问答知识库实验结论", "", "作业3 · 方向A · 2026年半年报", "",
                  f"公开仓库：{repository_url}", "",
                  "[10份官方半年度报告全文与校验值](https://github.com/leonardlee233/automotive-financial-rag/blob/main/DATA_SOURCES.md)；原始PDF不上传仓库。", "",
                  f"10家公司，1,765页官方财报；正文约800字、重叠120字，表格保留行列与口径。实测使用BGE-small-zh-v1.5 + BM25/RRF检索；前8题用本地Qwen3-4B-Instruct回答，跨公司两题用来源行结构化汇总。", "",
                  f"AI辅助答案判定：完全正确{counts['correct']}道（{counts['correct']/10:.0%}），部分正确{counts['partial']}道，错误{counts['wrong']}道。独立人工核验：尚未完成（0/10）。", "",
                  "## 召回与答案分开看", "",
                  "| 题号 | 融合候选来源 | 最终证据来源 | AI辅助答案判定 |", "|---|---:|---:|---|"]
    for row in rows:
        stage = audits[row["id"]]["stages"]
        fused, final = stage["fused_candidates"], stage["final_chunks"]
        conclusion.append(f"| {row['id']} | {fused['hits']}/{fused['total']} | {final['hits']}/{final['total']} | {row['ai_verdict']} |")
    conclusion.extend(["", "Q09融合候选只有7/10家公司，按公司补查表格后最终证据10/10；Q05、Q10显示来源命中也可能答不完整。候选池命中率不是答案正确率。", ""])
    for title, content in notes.items():
        conclusion.extend([f"## {title}", "", content, ""])
    conclusion.extend(["## 核验状态", "", "AI助手已对照原文辅助复核；独立人工核验尚未进行。请按 [独立核验表](https://github.com/leonardlee233/automotive-financial-rag/blob/main/evaluation/independent_human_review.md) 逐页填写核验人、日期、结论和差异。10题为开发集，不代表所有财报问题。", ""])
    (ROOT / "CONCLUSION.md").write_text("\n".join(conclusion), encoding="utf-8")
    submission = "方向：A\n代码仓库：" + repository_url + "\n一句话结论：" + notes["一句话结论"] + "\n"
    (ROOT / "SUBMISSION.txt").write_text(submission, encoding="utf-8")
    (ROOT / "outputs/submission_text.txt").write_text(submission, encoding="utf-8")
    (ROOT / "outputs/实验结论.md").write_text("\n".join(conclusion), encoding="utf-8")
    print(dict(counts))


if __name__ == "__main__":
    main()
