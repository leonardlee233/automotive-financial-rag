"""Small, auditable aggregation for two cross-company financial-report questions."""
from __future__ import annotations

import re
from collections import defaultdict
from decimal import Decimal


MONEY = re.compile(r"-?\d{1,3}(?:,\d{3})+(?:\.\d+)?|-?\d+\.\d+")
RISK_PATTERNS = {
    "市场竞争与毛利率": re.compile(r"市场竞争|产品竞争力|毛利率|客户降价|行业波动|市场需求"),
    "国际贸易与汇率": re.compile(r"关税|贸易|汇率|汇兑|国际.*市场"),
    "原材料与供应链": re.compile(r"原材料|供应链|供应商|采购成本"),
    "客户及回款": re.compile(r"客户集中|应收账款|客户违约|客户需求"),
    "技术与新业务": re.compile(r"技术升级|技术研发|产品开发|新产业"),
    "产品质量": re.compile(r"产品质量|质量责任|召回"),
    "ESG与合规": re.compile(r"ESG|环保|合规"),
}


def _metric_row(chunk: dict, metric: str) -> tuple[Decimal, str] | None:
    for line in chunk["text"].splitlines():
        label = line.split("|", 1)[0].strip()
        if metric == "revenue":
            if not re.match(r"^营业收入(?:（元）|\(元\))?\s*$", label):
                continue
        elif not ("归属于上市公司股东的净" in label and "扣除" not in label):
            continue
        numbers = MONEY.findall(line)
        if numbers:
            return Decimal(numbers[0].replace(",", "")), line.strip()
    return None


def summarize_financials(all_chunks: list[dict], companies: list[str]) -> tuple[str, list[dict], dict]:
    records = []
    evidence = []
    for company in companies:
        candidates = [c for c in all_chunks if c["company"] == company and c["page"] <= 10
                      and c["chunk_type"] == "table" and "主要会计数据" in (c.get("table_name") or "")]
        candidates.sort(key=lambda c: (c["page"], c["chunk_id"]))
        found = {}
        for metric in ("revenue", "profit"):
            options = [(c, _metric_row(c, metric)) for c in candidates]
            matches = [(c, hit) for c, hit in options if hit]
            if not matches:
                raise ValueError(f"No {metric} main-financial-data row for {company}")
            found[metric] = matches[0]
        revenue_chunk, revenue = found["revenue"]
        profit_chunk, profit = found["profit"]
        records.append({"company": company, "revenue": revenue[0], "profit": profit[0],
                        "revenue_page": revenue_chunk["page"], "profit_page": profit_chunk["page"]})
        for chunk in (revenue_chunk, profit_chunk):
            if chunk["chunk_id"] not in {e["chunk_id"] for e in evidence}:
                evidence.append(chunk)
    by_revenue = sorted(records, key=lambda r: r["revenue"], reverse=True)
    by_profit = sorted(records, key=lambda r: r["profit"], reverse=True)
    profit_rank = {r["company"]: i for i, r in enumerate(by_profit, 1)}
    lines = ["2026年上半年，金额单位为人民币元；取各公司半年度报告主要会计数据表的本报告期列。", "",
             "| 营收排名 | 公司 | 营业收入 | 归母净利润 | 归母排名 | PDF页码 |",
             "|---:|---|---:|---:|---:|---:|"]
    for i, r in enumerate(by_revenue, 1):
        page = f"{r['revenue_page']}" if r["revenue_page"] == r["profit_page"] else f"{r['revenue_page']}/{r['profit_page']}"
        lines.append(f"| {i} | {r['company']} | {r['revenue']:,.2f} | {r['profit']:,.2f} | {profit_rank[r['company']]} | {page} |")
    lines.append("")
    lines.append("归母净利润从高到低：" + "、".join(r["company"] for r in by_profit) + "。")
    lines.append("")
    top_rev, top_profit = by_revenue[0], by_profit[0]
    lines.append(f"差异：营收第一为{top_rev['company']}，归母净利第一为{top_profit['company']}；仅凭这张指标表不能断言具体业务原因，需另查各公司管理层讨论。")
    return "\n".join(lines), evidence, {"revenue_order": [r["company"] for r in by_revenue],
                                          "profit_order": [r["company"] for r in by_profit]}


def summarize_risks(retrieved: list[dict], companies: list[str]) -> tuple[str, list[dict], dict]:
    matches: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    evidence = []
    for chunk in retrieved:
        if chunk["company"] not in companies or "管理层" not in chunk["section"]:
            continue
        for line in chunk["text"].splitlines():
            line = line.strip()
            if "风险" not in line or len(line) > 130:
                continue
            for category, pattern in RISK_PATTERNS.items():
                if pattern.search(line):
                    bucket = matches[category][chunk["company"]]
                    if not any(row["chunk_id"] == chunk["chunk_id"] for row in bucket):
                        bucket.append(chunk)
                    if chunk["chunk_id"] not in {r["chunk_id"] for r in evidence}:
                        evidence.append(chunk)
    lines = ["仅归纳本轮检索到的管理层讨论风险段落；括号内为报告PDF页码。未检索到的公司或类别不推断。", ""]
    covered = set()
    for category, company_map in matches.items():
        if len(company_map) < 2:
            continue
        entries = []
        for company in companies:
            if company in company_map:
                pages = "/".join(str(p) for p in sorted({c["page"] for c in company_map[company]}))
                entries.append(f"{company}（第{pages}页）")
                covered.add(company)
        lines.append(f"{category}：" + "、".join(entries) + "。")
        lines.append("")
    missing = [c for c in companies if c not in covered]
    if missing:
        lines.append("本轮未能为下列公司找到可核验的共同类别：" + "、".join(missing) + "。")
    lines.append("这是按披露文字归类，不表示所有公司面对的风险程度相同；完整风险说明应回到所列原页核查。")
    return "\n".join(lines), evidence, {"covered_companies": sorted(covered), "missing_companies": missing}
