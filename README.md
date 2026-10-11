# 作业 3 · 方向 A：汽车零部件财报问答知识库

使用 10 家上市公司的 2026 年半年度报告全文，建立可提问、答案带出处的中文知识库。
**[公开 GitHub 仓库](https://github.com/leonardlee233/automotive-financial-rag)**（2026-10-11 无登录访问核验）。提交材料：代码、[问答页面截图](outputs/streamlit_screenshot.png)、[一页结论 PDF](outputs/one_page_conclusion.pdf)。

从这里查证：[10 份官方全文来源和下载校验](DATA_SOURCES.md) · [召回与答案分开评价](evaluation/retrieval_audit.md) · [10 题答案与完整检索轨迹](evaluation/results_optimized.jsonl) · [独立人工核验状态](evaluation/independent_human_review.md)。

## 数据

福耀玻璃、拓普集团、华域汽车、德赛西威、伯特利、星宇股份、均胜电子、新泉股份、保隆科技、旭升集团。全部为同一期官方完整 PDF，共 1,765 页。9 份来自巨潮资讯官方静态披露地址，德赛西威来自深交所：

| 公司 | 代码 | 官方全文 | PDF页数 |
|---|---|---|---:|
| 福耀玻璃 | 600660 | [巨潮 PDF](https://static.cninfo.com.cn/finalpage/2026-08-19/1225479532.PDF) | 142 |
| 拓普集团 | 601689 | [巨潮 PDF](https://static.cninfo.com.cn/finalpage/2026-08-28/1225521853.PDF) | 188 |
| 华域汽车 | 600741 | [巨潮 PDF](https://static.cninfo.com.cn/finalpage/2026-08-28/1225516573.PDF) | 149 |
| 德赛西威 | 002920 | [深交所 PDF](https://disc.static.szse.cn/disc/disk03/finalpage/2026-08-14/2aab2da4-0d48-471f-b396-fbded887d69c.PDF) | 144 |
| 伯特利 | 603596 | [巨潮 PDF](https://static.cninfo.com.cn/finalpage/2026-08-28/1225521940.PDF) | 249 |
| 星宇股份 | 601799 | [巨潮 PDF](https://static.cninfo.com.cn/finalpage/2026-08-27/1225509977.PDF) | 143 |
| 均胜电子 | 600699 | [巨潮 PDF](https://static.cninfo.com.cn/finalpage/2026-08-26/1225506436.PDF) | 240 |
| 新泉股份 | 603179 | [巨潮 PDF](https://static.cninfo.com.cn/finalpage/2026-08-04/1225454502.PDF) | 164 |
| 保隆科技 | 603197 | [巨潮 PDF](https://static.cninfo.com.cn/finalpage/2026-08-27/1225513711.PDF) | 166 |
| 旭升集团 | 603305 | [巨潮 PDF](https://static.cninfo.com.cn/finalpage/2026-08-28/1225520349.PDF) | 180 |

报告名、披露日期、完整 URL 和 SHA-256 见 [来源清单](DATA_SOURCES.md)、`config/reports.json` 与 `data/processed/download_manifest.json`。
不在仓库中附带原始 PDF；下载脚本检查 PDF 文件头和页数。

## 实现

- 正文约 800 字、120 字重叠，优先句末；保留公司、章节、PDF 页码、块序号。
- 表格按行列提取。按页面坐标寻找表格上方标题，不再用整页标题顺序猜表名；处理跨页延续。表格块不截断数字和行，重复表名、口径、单位与表头。标题或口径不明时明确标注，不强行猜测。
- 本次完整运行使用 BAAI/bge-small-zh-v1.5 语义向量，配合 jieba + rank_bm25，以 RRF(k=60) 融合。
- embedding 文本包含公司与章节。BGE 的长度限制通过 360 字/40 重叠的内部窗口、重复公司章节、归一化均值解决；检索和引用仍以原始约 800 字块为单位。
- 仍提供优先方案 Qwen3-Embedding-0.6B。已在本机加载并测试，但老款四核 CPU 处理 4 块约 22 秒，因此全库实测采用轻量 BGE。不能把本次成绩写成 Qwen 向量结果。
- 简单优化：自动识别公司、口语术语改写、排除反向口径、主要会计数据等元数据加权、重复证据去重；全景题按公司分别检索，不让单家公司占满证据。
- 在融合候选中按所问指标选择少量覆盖充分的证据，并筛选相关表格行；完整候选、最终证据和实际模型上下文分别保存，便于发现漏项。
- 回答器是本地 Qwen3-4B-Instruct-2507（Unsloth Q4_K_M 量化，llama.cpp b9380），没有训练或微调，也不是 GraphRAG/复杂 Agent。
- Q09/Q10 长证据在本机 CPU 上本地生成极慢，实测改用同一混合索引后的来源行结构化汇总：Q09逐公司读取主要会计数据表并计算双排名，Q10按管理层风险原文行归类；两题的 `answer_backend` 明确标注，不冒称为Qwen生成。
- 不再静默降级成截取原文。模型服务不可用时会报错；只有显式选择 ANSWER_BACKEND=extractive 才运行旧诊断摘录器，不能将其评测当作 LLM 成绩。

## 运行（Windows / Python 3.12）

在项目根目录运行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python scripts/download_reports.py
python scripts/parse_reports.py
python scripts/setup_local_models.py --light-embedding
python scripts/build_index.py --backend semantic --model BAAI/bge-small-zh-v1.5
python scripts/setup_local_models.py
.\scripts\start_local_llm.ps1
```

保留模型终端，另开终端运行：

```powershell
.\.venv\Scripts\Activate.ps1
python -m streamlit run app.py --server.address 127.0.0.1
```

浏览器打开 http://127.0.0.1:8501。首次下载回答模型约 2.5 GB；模型和运行程序均放 work/models，不进入 Git。
本地服务只监听 127.0.0.1，不对外网开放；CPU 上回答可能需要几分钟。

使用 Qwen 语义索引（更强的机器上推荐）：

```powershell
python scripts/setup_local_models.py --embedding
python scripts/build_index.py --backend qwen --model Qwen/Qwen3-Embedding-0.6B
```

模型切换后必须重新建索引、重启页面；查询和文档必须使用相同模型。索引按批次缓存，可中断后继续。
更换模型后的结果必须重新评测，不能直接沿用已提交分数。

## 评测与评分

```powershell
python scripts/evaluate.py
python scripts/evaluate_panorama.py
python scripts/audit_retrieval.py
python -m pytest -q
```

10 道原题不变，含 2 道跨公司题。每题记录原问法、检索问法、两路完整候选、融合候选、最终块全文、回答、模型配置、索引/回答摘要哈希。先核对报告、期间、单位、表名、合并/母公司口径与 PDF 原页，再评价答案。

**召回与答案分开算：**[逐题召回审计](evaluation/retrieval_audit.md)按固定来源页/公司核对。Q01–Q08 最终证据各命中 1/1；Q09 融合候选只覆盖 7/10 家，逐公司补查表格后最终证据 10/10；Q10 最终证据 10/10。来源命中不等于答案正确：Q05 把 14.40% 写成 14.40 成，Q09 缺经营差异原文解释，Q10 风险归类有边界。Vector/BM25 是较大的候选池，候选命中也不能冒充 Top-K 答对。

**答案判定：**7/10 完全正确、3/10 部分正确；partial 不算正确。这是用于优化的开发题集，不是未知题的泛化正确率。`manual_verdict` 是早期兼容字段，实际含义是 **AI 助手对照原文后的辅助判定**，新字段 `ai_verdict` 明确标注。

**独立人工核验：尚未完成（0/10）。** 不能把 AI 辅助判定称作独立人工评审。[独立核验表](evaluation/independent_human_review.md)留给用户或老师逐页填写核验人、日期、判定及差异；在填完前不报告“人工正确率”。

评测脚本先把新答案记为 pending，不会自动编造评分。AI 助手辅助逐题对照原报告后，将 verdict、reason、sources 和对应 answer_sha256 写入 review 文件，再执行：

```powershell
python scripts/review_evaluation.py evaluation/results_optimized.jsonl evaluation/review_optimized.json
python scripts/export_evaluation.py
python scripts/export_conclusion_pdf.py
python scripts/validate_project.py
python scripts/package_project.py
```

表格口径的核验不能只看页码：Q02 要核对第42页**合并利润表**，避免同页母公司表；Q06 所引的是第25页“母公司报表中期末未分配利润为人民币216,288,909.09元”的叙述句，不能把同页表头的“万元”套到该句；Q05 来源表未明确合并口径，回答中的“合并口径”缺依据。
evaluation/results_base.* 和 results_rewrite.* 是旧版“哈希向量 + 截取原文”的失败原型记录，仅作历史追踪，不用于证明真实语义 RAG 的一般能力。

## 交付文件

- outputs/automotive_financial_rag_assignment.zip：可复现项目代码包。
- outputs/one_page_conclusion.pdf：一页结论。
- outputs/streamlit_screenshot.png：真实页面截图；另附检索过程截图。
- outputs/submission_text.txt：题目要求的三行文本；仓库地址来自 config/submission.json。
- CONCLUSION.md：与 PDF 对应的结论 Markdown。
- evaluation/results_optimized.*：逐题实测、评分与出处。

## 密钥与安全

本地默认不需要任何 API key。可选 API 模式设置 ANSWER_BACKEND=openai、OPENAI_API_KEY 和 OPENAI_MODEL；
建议只设进程环境变量。提供 .env.example 空模板，未写入任何真实密钥；.env 已列入 .gitignore。
评测记录不保存请求认证头；仓库、截图、日志不得出现密钥或私人账号。
模型下载、原始报告、索引和临时缓存都不打入代码 ZIP。

## 已知限制

PDF 跨页表头、合并单元格和段内章节切换仍需抽查；“口径未明确”不等于合并口径。
多子问题需要每项证据都在上下文中；全景题即使覆盖10家公司，也可能漏掉风险类别或缺少经营差异的解释材料。
小模型可能算错比例、混淆研发费用与总投入，引用页码也应核对。具体失误以本次逐题结果为准。

## 模型说明与来源

- [Qwen3-Embedding 官方说明](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B)
- [BGE 官方模型说明](https://huggingface.co/BAAI/bge-small-zh-v1.5)
- [Qwen3-4B-Instruct 原始模型](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507)
- [实际使用的 Unsloth 量化](https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF)
- [llama.cpp 官方运行程序](https://github.com/ggml-org/llama.cpp/releases/tag/b9380)

