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
    counts = Counter(r["manual_verdict"] for r in results)
    font_path = Path("C:/Windows/Fonts/msyh.ttc")
    if not font_path.exists():
        raise RuntimeError("Set a usable Chinese font path before exporting.")
    pdfmetrics.registerFont(TTFont("CJK", str(font_path)))
    navy = colors.HexColor("#17324D")
    body = ParagraphStyle("body", fontName="CJK", fontSize=9, leading=14, textColor=navy, spaceAfter=5)
    title = ParagraphStyle("title", parent=body, fontSize=19, leading=25, spaceAfter=8)
    small = ParagraphStyle("small", parent=body, fontSize=8, leading=11)
    heading = ParagraphStyle("heading", parent=body, fontSize=11, leading=15, spaceBefore=8)
    p = lambda s, style=body: Paragraph(escape(s), style)
    output = ROOT / "outputs/one_page_conclusion.pdf"
    doc = SimpleDocTemplate(str(output), pagesize=A4, leftMargin=16*mm, rightMargin=16*mm,
                            topMargin=14*mm, bottomMargin=12*mm, title="汽车零部件财报问答知识库实验结论")
    story = [p("汽车零部件财报问答知识库", title),
             p("作业 3 · 方向 A｜2026 年半年度报告｜一页实验结论", small),
             p(f"实测：10 道原题，完全正确 {counts['correct']} 道（{counts['correct']/10:.0%}），部分正确 {counts['partial']} 道，错误 {counts['wrong']} 道。部分正确不计入正确率。"),
             p("材料与做法", heading),
             p("福耀、拓普、华域、德赛西威、伯特利、星宇、均胜、新泉、保隆、旭升共10家公司，1,765页官方完整半年报。正文约800字切块、重叠120字；表格保留行列、表名、单位、口径和页码。"),
             p("BGE-small-zh-v1.5语义向量 + jieba/BM25，RRF融合；术语改写、口径筛选及跨公司分组检索。前8题用本地Qwen3-4B-Instruct回答；跨公司两题采用可追溯的表格行汇总/风险原文行归类。仓库另支持Qwen3-Embedding-0.6B。"),
             p("10 道题实际结果", heading)]
    labels = {"correct":"正确", "partial":"部分正确", "wrong":"错误"}
    cells = [[p("题号", small), p("问题类型", small), p("结果", small), p("核验要点 / 失误", small)]]
    for row in results:
        cells.append([p(row["id"],small), p(row["type"],small), p(labels[row["manual_verdict"]],small),
                      p(row.get("review_short", row["reason"])[:90],small)])
    table = Table(cells, colWidths=[15*mm,30*mm,23*mm,110*mm])
    table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#EAF1F8")),
                               ("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#BFCBDA")),
                               ("VALIGN",(0,0),(-1,-1),"TOP"),
                               ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3)]))
    story.append(table)
    notes = json.loads((ROOT / "evaluation/conclusion_notes.json").read_text(encoding="utf-8"))
    for name in ["哪类题答得好", "哪类题仍会出错，为什么", "一句话结论"]:
        story.extend([p(name, heading), p(notes[name])])
    story.extend([Spacer(1,2*mm),p("核验说明：助手逐题对照原财报复核，尚非独立人工评审。10题用于开发调试，正确率仅代表本题集，不代表所有财报问题。逐题回答、双路召回和最终证据均已保存。",small)])
    doc.build(story)
    print(output)

if __name__ == "__main__":
    main()

