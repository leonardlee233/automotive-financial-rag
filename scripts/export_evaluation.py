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
    counts = Counter(r["manual_verdict"] for r in rows)
    lines = ["# 财报问答：10道原题实际结果", "",
             f"完全正确 {counts['correct']}/10；部分正确 {counts['partial']}；错误 {counts['wrong']}。partial 不计入正确率。", "",
             "评分为助手对照原文的复核，尚无独立人工复核。该题集用于优化，不是未知题的泛化测试。", ""]
    for row in rows:
        lines.extend([f"## {row['id']} · {row['type']} · {row['manual_verdict']}", "",
                      row["question"], "", row["answer"], "", "### 核验", "", row["reason"], "",
                      f"错误类型：{row['error_type']}", "", "### 最终证据块", ""])
        for chunk in row["final_chunks"]:
            lines.append(f"- {chunk['chunk_id']}｜{chunk['company']}｜PDF第{chunk['page']}页｜{chunk.get('table_name') or chunk['section']}")
        lines.extend(["", "完整 Vector/BM25 候选、最终证据全文、模型配置和哈希见同名 JSONL。", ""])
    (ROOT / "evaluation/results_optimized.md").write_text("\n".join(lines), encoding="utf-8")
    with (ROOT / "evaluation/results_optimized.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        fields = ["id", "type", "question", "answer", "manual_verdict", "error_type", "reason"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({key: row[key] for key in fields} for row in rows)
    notes = read_json(ROOT / "evaluation/conclusion_notes.json")
    conclusion = ["# 汽车零部件财报问答知识库实验结论", "", "作业3 · 方向A · 2026年半年报", "",
                  f"10家公司，1,765页官方财报；正文约800字、重叠120字，表格保留行列与口径。实测使用BGE-small-zh-v1.5 + BM25/RRF检索；前8题用本地Qwen3-4B-Instruct回答，跨公司两题用来源行结构化汇总。", "",
                  f"10道原题：完全正确{counts['correct']}道（{counts['correct']/10:.0%}），部分正确{counts['partial']}道，错误{counts['wrong']}道。", ""]
    for title, content in notes.items():
        conclusion.extend([f"## {title}", "", content, ""])
    conclusion.extend(["## 逐题结果", "", "| 题号 | 类型 | 结果 |", "|---|---|---|"])
    conclusion.extend(f"| {r['id']} | {r['type']} | {r['manual_verdict']} |" for r in rows)
    conclusion.extend(["", "助手已对照原文复核，用户可按页码抽查；10题为开发集，不代表所有财报问题。", ""])
    (ROOT / "CONCLUSION.md").write_text("\n".join(conclusion), encoding="utf-8")
    submission_config = ROOT / "config/submission.json"
    repository_url = read_json(submission_config).get("repository_url", "").strip() if submission_config.exists() else ""
    if not repository_url:
        repository_url = "[待填写：上传代码后的真实 GitHub 或 cnb.cool 仓库 URL]"
    submission = "方向：A\n代码仓库：" + repository_url + "\n一句话结论：" + notes["一句话结论"] + "\n"
    (ROOT / "SUBMISSION.txt").write_text(submission, encoding="utf-8")
    (ROOT / "outputs/submission_text.txt").write_text(submission, encoding="utf-8")
    (ROOT / "outputs/实验结论.md").write_text("\n".join(conclusion), encoding="utf-8")
    print(dict(counts))


if __name__ == "__main__":
    main()
