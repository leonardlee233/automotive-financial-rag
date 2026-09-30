from __future__ import annotations
import re


def rewrite_query(query: str) -> str:
    """Small, transparent terminology normalization for the course ablation."""
    rewritten = re.split(r"不要|请勿|别拿|而非", query)[0]
    replacements = {
        "卖了多少钱": "营业收入",
        "技术开发": "研发费用",
        "归母净利润": "归属于上市公司股东的净利润",
        "经营现金流": "经营活动产生的现金流量净额",
        "经营活动现金流量净额": "经营活动产生的现金流量净额",
        "前两个季度": "上半年",
        "增减几成": "上年同期 变动比例",
    }
    for source, target in replacements.items():
        rewritten = rewritten.replace(source, target)
    if any(term in rewritten for term in ("营业收入", "归属于上市公司股东的净利润", "经营活动产生的现金流量净额")):
        rewritten += " 主要会计数据 本报告期 上年同期 同比增减"
    if "合并利润表" in rewritten:
        rewritten += " 合并利润表 项目 附注 2026年半年度 单位"
    if "研发投入" in rewritten or "研发费用" in rewritten:
        rewritten += " 研发投入 研发费用 本期数 上年同期数 变动比例 占营业收入比例"
    return " ".join(rewritten.split())

