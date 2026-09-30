from src.common import ROOT, read_json


def test_ten_unique_companies_and_full_reports():
    reports = read_json(ROOT / "config" / "reports.json")
    assert len(reports) == 10
    assert len({item["stock_code"] for item in reports}) == 10
    assert all("摘要" not in item["report"] for item in reports)
    assert all(item["url"].lower().endswith(".pdf") for item in reports)

