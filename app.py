from __future__ import annotations

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from src.answering import answer_openai, select_evidence
from src.common import ROOT, read_json, read_jsonl
from src.retrieval import HybridRetriever
from src.querying import rewrite_query
from src.panorama import summarize_financials, summarize_risks

load_dotenv()
st.set_page_config(page_title="汽车零部件财报 RAG", page_icon="📑", layout="wide")

st.title("汽车零部件上市公司 2026H1 财报问答")
st.caption("向量 + BM25 混合检索（RRF）｜回答带公司、章节、PDF页码与块编号")


@st.cache_resource
def load_retriever() -> HybridRetriever:
    return HybridRetriever()


reports = read_json(ROOT / "config" / "reports.json")
companies = ["全部公司"] + [item["company"] for item in reports]
with st.sidebar:
    results_path = ROOT / "evaluation/results_optimized.jsonl"
    saved_results = read_jsonl(results_path) if results_path.exists() else []
    replay = st.checkbox("查看已保存的真实评测", value=bool(st.query_params.get("review")), disabled=not saved_results)
    saved_row = None
    if replay:
        ids = [r["id"] for r in saved_results]
        chosen = st.selectbox("评测题号", ids, index=ids.index(st.query_params.get("review")) if st.query_params.get("review") in ids else 0)
        saved_row = next(r for r in saved_results if r["id"] == chosen)
    st.header("检索设置")
    company = st.selectbox("公司范围", companies)
    top_k = st.slider("最终证据块", 3, 12, 6)
    use_rewrite = st.checkbox("启用术语改写、口径筛选和跨公司检索", value=True, help="透明规则增强普通混合检索，不调用 Agent。")
    st.markdown("**当前回答器**")
    st.write(("OpenAI API" if os.getenv("OPENAI_API_KEY") else "本地 Qwen3-4B-Instruct（无需密钥）") + "；跨公司排名/风险题使用来源行汇总")
    st.info("表格问题请检查表名、单位及合并/母公司口径。")

examples = [
    "均胜电子2026年上半年研发投入及占收入比例是多少？",
    "福耀玻璃合并利润表里的营业收入是多少？",
    "德赛西威上半年研发投入和占营收比例是多少？",
    "综合10家公司管理层讨论，归纳共同经营风险。",
]
question = st.text_area("问题", value=saved_row["question"] if saved_row else examples[0], height=90, disabled=bool(saved_row))
auto_demo = st.query_params.get("demo") == "1"
if st.button("检索并回答", type="primary", width="stretch", disabled=bool(saved_row)) or auto_demo or saved_row:
    with st.spinner("正在检索财报原文..."):
        if saved_row:
            st.info(f"真实评测回放 · {saved_row['id']} · {saved_row['run_id']}；显示当次回答与检索记录，不重新生成。")
            trace = {"final": saved_row["final_chunks"], "vector": saved_row["vector_recall"], "bm25": saved_row["bm25_recall"]}
            answer = saved_row["answer"]
            retrieval_query = saved_row["retrieval_query"]
            embedding_model = saved_row["embedding_model"]
        else:
            try:
                retriever = load_retriever()
                retrieval_query = rewrite_query(question) if use_rewrite else question
                trace = retriever.search(question, None if company == "全部公司" else company, top_k=top_k, candidate_k=80, optimized=use_rewrite)
                panoramic = company == "全部公司" and any(term in question for term in ("10家公司", "十家公司", "所有公司"))
                if panoramic and "风险" in question:
                    answer, evidence, _ = summarize_risks(trace["final"], sorted({row["company"] for row in retriever.chunks}))
                    trace["final"] = [{**chunk, "rank": rank} for rank, chunk in enumerate(evidence, 1)]
                elif panoramic and "营业收入" in question and "净利润" in question:
                    answer, evidence, _ = summarize_financials(retriever.chunks, sorted({row["company"] for row in retriever.chunks}))
                    trace["final"] = [{**chunk, "rank": rank} for rank, chunk in enumerate(evidence, 1)]
                else:
                    if use_rewrite:
                        trace['final'] = select_evidence(question, trace['final'])
                    answer = answer_openai(question, trace["final"])
                embedding_model = retriever.embedding_model
            except Exception:
                st.error("问答未完成：请确认索引已经建立，本地模型服务正在运行；未自动降级为摘录回答。可在侧栏查看已有真实评测。")
                st.stop()
    if use_rewrite and retrieval_query != question:
        st.caption(f"检索改写：{retrieval_query}")
    st.subheader("回答")
    st.caption(f"语义向量：{Path(embedding_model).name}｜BM25：jieba｜融合：RRF")
    st.markdown(answer)
    st.subheader("最终证据")
    for item in trace["final"]:
        label = f"#{item['rank']} {item['company']}｜{item['section']}｜PDF第{item['page']}页｜{item['chunk_id']}"
        with st.expander(label, expanded=item["rank"] <= 2):
            if item.get("chunk_type") == "table":
                st.caption(f"表格：{item.get('table_name')}｜口径：{item.get('statement_scope')}")
            st.text(item["text"])
    st.subheader("检索过程")
    left, right = st.columns(2)
    with left:
        st.markdown("**Vector 召回**")
        st.dataframe([{k: row.get(k) for k in ("rank", "score", "company", "page", "chunk_id")} for row in trace["vector"]], width="stretch")
    with right:
        st.markdown("**BM25 召回**")
        st.dataframe([{k: row.get(k) for k in ("rank", "score", "company", "page", "chunk_id")} for row in trace["bm25"]], width="stretch")
else:
    st.info("选择公司范围并输入问题。跨公司全景题建议选择“全部公司”。")

