from scripts.parse_reports import clean_cell, row_chunks, geometry_title
from src.querying import rewrite_query


def test_wrapped_cells_preserve_numbers():
    assert clean_cell("1,186,296,\n692.93") == "1,186,296,692.93"
    assert clean_cell("营业\n收入") == "营业收入"


def test_table_chunks_repeat_headers_and_keep_rows():
    rows = ["项目 | 2026年半年度 | 2025年半年度"] + [f"项目{i} | 123,456.78 | 987,654.32" for i in range(100)]
    chunks = list(row_chunks("\n".join(rows), size=200))
    assert len(chunks) > 1
    assert all(c.startswith(rows[0]) for c in chunks)
    assert [line for c in chunks for line in c.splitlines()[1:]] == rows[1:]


def test_negative_scope_not_in_search():
    query = rewrite_query("福耀玻璃合并利润表营业收入是多少？不要给我母公司利润表数字")
    assert "合并利润表" in query
    assert "母公司" not in query


def test_title_uses_only_preceding_geometry():
    class Crop:
        def extract_text(self):
            return "母公司资产负债表\n单位：元"
    class Page:
        width = 600
        def crop(self, bbox):
            assert bbox[3] == 100
            return Crop()
    class Table:
        bbox = (10, 100, 580, 300)
    assert geometry_title(Page(), Table(), None, 0) == ("母公司资产负债表", "母公司", "单位：元")
