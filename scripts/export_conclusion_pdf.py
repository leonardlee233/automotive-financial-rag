from __future__ import annotations
import json
from collections import Counter
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]

def main():
    results = [json.loads(s) for s in (ROOT / "evaluation/results_optimized.jsonl").read_text(encoding="utf-8").splitlines() if s.strip()]
    if len(results) != 10 or any(r["manual_verdict"] == "pending" for r in results):
        raise ValueError("Export only after all 10 real answers have been reviewed.")
    if any(r.get("independent_human_review") != "not_done" for r in results):
        raise ValueError("Recheck independent human review status before export.")
    counts = Counter(r["ai_verdict"] for r in results)
    audit = {r["id"]: r for r in json.loads((ROOT / "evaluation/retrieval_audit.json").read_text(encoding="utf-8"))}
    reports = json.loads((ROOT / "data/processed/download_manifest.json").read_text(encoding="utf-8"))
    repository_url = json.loads((ROOT / "config/submission.json").read_text(encoding="utf-8"))["repository_url"]
    font_path = Path("C:/Windows/Fonts/msyh.ttc")
    if not font_path.exists():
        raise RuntimeError("Set a usable Chinese font path before exporting.")
    pdfmetrics.registerFont(TTFont("CJK", str(font_path)))
    navy = colors.HexColor("#17324D")
    body = ParagraphStyle("body", fontName="CJK", fontSize=9.2, leading=13, textColor=navy, spaceAfter=5)
    title = ParagraphStyle("title", parent=body, fontSize=19, leading=25, spaceAfter=5)
    small = ParagraphStyle("small", parent=body, fontSize=8.1, leading=11.2, spaceAfter=3)
    heading = ParagraphStyle("heading", parent=body, fontSize=11, leading=15, spaceBefore=8, spaceAfter=4)
    p = lambda s, style=body: Paragraph(escape(s), style)
    link = lambda label, url: Paragraph(f'<link href="{escape(url, {chr(34): "&quot;"})}" color="#1462A0">{escape(label)}</link>', small)
    output = ROOT / "outputs/one_page_conclusion.pdf"
    doc = SimpleDocTemplate(str(output), pagesize=A4, leftMargin=15*mm, rightMargin=15*mm,
                            topMargin=12*mm, bottomMargin=11*mm, title="汽车零部件财报问答知识库实验结论")
    story = [p("汽车零部件财报问答知识库", title),
             p("作业 3 · 方向 A｜2026 年半年度报告｜一页结论", small),
             link(repository_url, repository_url),
             p("10 份官方全文来源（点击“全文 PDF”可打开原报告）", heading)]
    source_cells = [[p("公司 / 代码", small), p("披露渠道", small), p("PDF页数", small), p("官方全文", small)]]
    for report in reports:
        channel = "深交所" if "szse.cn" in report["url"] else "巨潮资讯"
        source_cells.append([p(f"{report['company']} {report['stock_code']}", small), p(channel, small),
                             p(str(report["pages"]), small), link("全文 PDF", report["url"])])
    source_table = Table(source_cells, colWidths=[58*mm, 44*mm, 26*mm, 52*mm])
    table_style = [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF1F8")),
                   ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD6E1")),
                   ("VALIGN", (0, 0), (-1, -1), "TOP"),
                   ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    source_table.setStyle(TableStyle(table_style))
    story.extend([source_table,
                  p("共 1,765 页；完整 URL、披露日期、SHA-256 和下载脚本见公开仓库 DATA_SOURCES.md。正文约800字切块并保留章节页码，表格保留行列、单位和口径；BGE向量 + jieba/BM25，经RRF融合。", small),
                  p("来源召回与答案表现分开评价", heading)])
    labels = {"correct": "正确", "partial": "部分", "wrong": "错误"}
    cells = [[p("题号", small), p("题型", small), p("融合候选", small), p("最终证据", small), p("AI答案判定 / 失误", small)]]
    for row in results:
        stages = audit[row["id"]]["stages"]
        fused = stages["fused_candidates"]
        final = stages["final_chunks"]
        cells.append([p(row["id"], small), p(row["type"], small),
                      p(f"{fused['hits']}/{fused['total']}", small), p(f"{final['hits']}/{final['total']}", small),
                      p(f"{labels[row['ai_verdict']]}：{row.get('review_short', row['reason'])[:46]}", small)])
    table = Table(cells, colWidths=[16*mm, 28*mm, 24*mm, 24*mm, 88*mm])
    table.setStyle(TableStyle(table_style))
    story.append(table)
    notes = json.loads((ROOT / "evaluation/conclusion_notes.json").read_text(encoding="utf-8"))
    story.extend([p("Q09 融合候选只覆盖 7/10 家；逐公司补查主要会计数据表后，最终证据达到 10/10。Q10 最终证据覆盖 10/10，风险归类仍有边界。候选命中不等于答对。", small),
                  p("口径、复核与结论", heading),
                  p("Q02 核对福耀第42页合并利润表；Q06 按保隆第25页“母公司报表…人民币…元”的叙述句核对，不套用同页表头的“万元”。Q05 原表未明示合并口径，且模型把14.40%误写成14.40成。", small),
                  p(f"AI助手对原页的辅助判定：完全正确 {counts['correct']}/10（{counts['correct']/10:.0%}），部分正确 {counts['partial']}/10；独立人工核验：未完成（0/10），不能把前者称为人工正确率。", body),
                  p(notes["一句话结论"], body),
                  p("10题为开发题集；完整双路召回、逐题答案、来源清单和独立人工核验空表均在公开仓库。", small)])
    doc.build(story)
    print(output)

if __name__ == "__main__":
    main()

