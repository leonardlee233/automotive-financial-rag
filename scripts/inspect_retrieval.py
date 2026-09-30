"""Retrieve all questions without generation, for transparent error diagnosis."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import ROOT, read_json, write_jsonl
from src.retrieval import HybridRetriever

retriever = HybridRetriever()
rows = []
for question in read_json(ROOT / 'config/questions.json'):
    trace = retriever.search(question['question'], question.get('company'), top_k=6, candidate_k=80)
    rows.append({'id': question['id'], **trace})
    print(question['id'], [(c['company'], c['page'], c.get('table_name')) for c in trace['final']], flush=True)
write_jsonl(ROOT / 'work/retrieval_diagnostic.jsonl', rows)
