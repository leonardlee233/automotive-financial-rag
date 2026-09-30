from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pdfplumber

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.chunking import chunk_text
from src.common import ROOT, normalize_text, read_json, write_jsonl

SECTION_RE = re.compile(r"^(第[一二三四五六七八九十百]+节\s*[^\n]{1,40})")
TABLE_HINT_RE = re.compile(r"(合并|母公司)?[^\n]{0,18}(资产负债表|利润表|现金流量表|所有者权益变动表|主要会计数据|研发投入|分行业|分产品|分地区|资产及负债状况|科目变动分析表|主要财务数据同比变动情况)[^\n]{0,20}")


def clean_cell(cell: object) -> str:
    value = str(cell or "")
    # PDF wraps both Chinese labels and digits inside cells. Neither needs a space.
    return normalize_text(value.replace("\n", ""))


def row_chunks(body: str, size: int = 800):
    """Keep whole rows and repeat the column header, never cut a number in half."""
    rows = body.splitlines()
    header_end = 0
    for index, row in enumerate(rows[:4]):
        if any(word in row for word in ("本期", "本报告期", "上年", "2026", "2025")):
            header_end = index + 1
    header = rows[:header_end]
    current = []
    for row in rows[header_end:]:
        if current and len("\n".join(header + current + [row])) > size:
            yield "\n".join(header + current)
            current = []
        current.append(row)
    if current or header:
        yield "\n".join(header + current)


def geometry_title(page, table, previous, previous_bottom):
    # Only inspect text ABOVE this table. A later title must never label an earlier table.
    top = max(0, previous_bottom)
    bottom = max(top, table.bbox[1])
    context = page.crop((0, top, page.width, bottom)).extract_text() if bottom > top else ""
    lines = (context or "").splitlines()
    candidates = [line.strip() for line in lines if TABLE_HINT_RE.search(line) and len(line) < 60 and not line.rstrip().endswith("。")]
    title = candidates[-1] if candidates else ""
    if not title and previous and table.bbox[1] < 150:
        title = previous[0]
    if not title:
        title = "未识别表名（请核对原页）"
    scope = "母公司" if "母公司" in title else "合并" if "合并" in title else "未明确"
    units = [line.strip() for line in lines if "单位" in line or "币种" in line]
    unit = "；".join(units[-2:])
    if not unit and previous and title == previous[0]:
        unit = previous[2]
    return title, scope, unit


def table_to_markdown(table: list[list[object]]) -> str:
    rows = [[clean_cell(cell) for cell in row] for row in table if any(clean_cell(cell) for cell in row)]
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    rows = [row + [""] * (width - len(row)) for row in rows]
    used_columns = [i for i in range(width) if any(row[i] for row in rows)]
    rows = [[row[i] for i in used_columns] for row in rows]
    return "\n".join(" | ".join(row) for row in rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-pages", type=int, default=0, help="Debug only; 0 parses all pages")
    args = parser.parse_args()
    manifest = read_json(ROOT / "data" / "processed" / "download_manifest.json")
    pages_out, chunks_out = [], []
    for report in manifest:
        pdf_path = ROOT / "data" / "raw" / report["file"]
        current_section = "封面及目录"
        per_report_seq = 0
        previous_table = None
        print(f"Parsing {report['company']} ({report['pages']} pages) ...", flush=True)
        with pdfplumber.open(pdf_path) as pdf:
            pages = pdf.pages[: args.max_pages or None]
            for page_no, page in enumerate(pages, 1):
                raw_text = page.extract_text(x_tolerance=2, y_tolerance=3) or ""
                text = normalize_text(raw_text)
                for line in text.splitlines():
                    match = SECTION_RE.match(line.strip())
                    if match:
                        current_section = match.group(1)
                page_record = {
                    "stock_code": report["stock_code"], "company": report["company"],
                    "report": report["report"], "section": current_section,
                    "page": page_no, "text": text,
                }
                pages_out.append(page_record)
                for piece in chunk_text(text, size=800, overlap=120):
                    per_report_seq += 1
                    chunks_out.append({
                        **page_record,
                        "chunk_id": f"{report['stock_code']}_2026H1_p{page_no:03d}_{per_report_seq:04d}",
                        "chunk_type": "text",
                        "table_name": None,
                        "statement_scope": None,
                        "text": piece,
                        "embedding_text": f"公司：{report['company']}\n章节：{current_section}\n{piece}",
                    })
                try:
                    tables = page.find_tables() or []
                except Exception as exc:
                    print(f"WARN table extraction {report['company']} p{page_no}: {exc}")
                    tables = []
                previous_bottom = 0
                for table_index, table in enumerate(tables):
                    body = table_to_markdown(table.extract())
                    if not body:
                        continue
                    title, scope, unit = geometry_title(page, table, previous_table, previous_bottom)
                    previous_bottom = table.bbox[3]
                    previous_table = (title, scope, unit)
                    prefix = (
                        f"公司：{report['company']}\n报告：{report['report']}\n章节：{current_section}\n"
                        f"表格：{title}\n口径：{scope}\n单位：{unit or '请核对原页'}\nPDF页码：{page_no}\n"
                    )
                    for part_index, piece in enumerate(row_chunks(body), 1):
                        per_report_seq += 1
                        table_text = prefix + piece
                        chunks_out.append({
                            **page_record,
                            "chunk_id": f"{report['stock_code']}_2026H1_p{page_no:03d}_t{table_index + 1:02d}_{part_index:02d}",
                            "chunk_type": "table",
                            "table_name": title,
                            "statement_scope": scope,
                            "unit": unit,
                            "bbox": list(table.bbox),
                            "text": table_text,
                            "embedding_text": f"公司：{report['company']}\n章节：{current_section}\n{table_text}",
                        })
        print(f"Finished {report['company']}", flush=True)
    write_jsonl(ROOT / "data" / "processed" / "pages.jsonl", pages_out)
    write_jsonl(ROOT / "data" / "processed" / "chunks.jsonl", chunks_out)
    print(f"Wrote {len(pages_out)} pages and {len(chunks_out)} chunks.")


if __name__ == "__main__":
    main()

