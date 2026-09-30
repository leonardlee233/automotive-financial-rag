from src.answering import select_evidence, format_sources


def chunk(cid, text, company='甲', title='主要会计数据'):
    return {'chunk_id':cid,'company':company,'text':text,'chunk_type':'table',
            'table_name':title,'section':'财务指标','page':1}


def test_select_evidence_covers_all_requested_fields():
    rows = [chunk('a','营业收入 | 100 | 90'),chunk('b','研发投入 | 20 | 18')]
    selected = select_evidence('研发投入及占营业收入比例是多少？',rows)
    assert {r['chunk_id'] for r in selected} == {'a','b'}


def test_explicit_statement_priority():
    rows = [chunk('a','营业收入 | 100'),chunk('b','营业收入 | 100',title='合并利润表')]
    assert select_evidence('合并利润表营业收入？不要母公司',rows)[0]['chunk_id'] == 'b'


def test_cross_company_context_has_every_company():
    rows = [chunk('a','营业收入 | 100',company='甲'),chunk('b','营业收入 | 200',company='乙')]
    assert len(select_evidence('所有公司营业收入排名',rows)) == 2
    assert 'PDF第1页' in format_sources(rows,'营业收入')


def test_parent_attribution_is_not_parent_scope():
    rows = [chunk('a','归属于母公司所有者的净利润 | 20\n期末未分配利润 | 900'),
            chunk('b','公司母公司报表中期末未分配利润为100元')]
    assert select_evidence('母公司口径期末未分配利润是多少？',rows)[0]['chunk_id'] == 'b'
