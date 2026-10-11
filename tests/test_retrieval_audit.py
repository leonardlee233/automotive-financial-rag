from scripts.audit_retrieval import matches


def test_consolidated_table_requires_scope_and_name():
    expected = {"company": "福耀玻璃", "page": 42, "table_name_contains": "合并利润表", "scope": "合并"}
    chunk = {"company": "福耀玻璃", "page": 42, "table_name": "母公司利润表", "statement_scope": "母公司"}
    assert not matches(chunk, expected)
    chunk.update(table_name="合并利润表", statement_scope="合并")
    assert matches(chunk, expected)


def test_parent_company_sentence_required_even_on_right_page():
    expected = {"company": "保隆科技", "page": 25, "text_contains": "母公司报表中期末未分配利润"}
    chunk = {"company": "保隆科技", "page": 25, "text": "合并未分配利润"}
    assert not matches(chunk, expected)
    chunk["text"] = "公司母公司报表中期末未分配利润为人民币216,288,909.09元"
    assert matches(chunk, expected)
