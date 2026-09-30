import numpy as np
from rank_bm25 import BM25Okapi
from src import retrieval


def test_fusion_trace_and_company_scope(monkeypatch):
    retriever = retrieval.HybridRetriever.__new__(retrieval.HybridRetriever)
    retriever.chunks = [
        {"chunk_id":"a", "company":"甲公司", "section":"主要会计数据", "text":"营业收入 100 主要会计数据", "statement_scope":"合并"},
        {"chunk_id":"b", "company":"甲公司", "section":"财务报告", "text":"营业收入 200 母公司", "statement_scope":"母公司"},
        {"chunk_id":"c", "company":"乙公司", "section":"财务报告", "text":"营业收入 300", "statement_scope":"合并"},
    ]
    retriever.vectors = np.array([[1,0],[0.9,0.1],[0.9,0.1]])
    retriever.embedding_backend = "semantic"
    retriever.embedding_model = "test"
    retriever.bm25 = BM25Okapi([retrieval.tokenize(c['text']) for c in retriever.chunks])
    monkeypatch.setattr(retrieval, 'embed_texts', lambda *a, **kw: (np.array([[1,0]]), 'test'))
    trace = retriever.search("甲公司合并营业收入，不要母公司数字")
    assert [c['chunk_id'] for c in trace['final']] == ['a']
    assert trace['final'][0]['selection_score'] >= trace['final'][0]['rrf_score']
    assert "母公司" not in trace['query']
