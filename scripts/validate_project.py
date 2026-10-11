from __future__ import annotations

import json
import re
import hashlib
from urllib.parse import urlparse
from collections import Counter
from pathlib import Path

from PIL import Image
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]


def jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    reports = json.loads((ROOT / "config" / "reports.json").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "data" / "processed" / "download_manifest.json").read_text(encoding="utf-8"))
    chunks = jsonl(ROOT / "data" / "processed" / "chunks.jsonl")
    results = jsonl(ROOT / "evaluation" / "results_optimized.jsonl")
    retrieval_audit = json.loads((ROOT / "evaluation" / "retrieval_audit.json").read_text(encoding="utf-8"))
    sources = (ROOT / "DATA_SOURCES.md").read_text(encoding="utf-8")
    assert len(reports) == len(manifest) == 10
    assert all(urlparse(r['url']).hostname in {'static.cninfo.com.cn', 'disc.static.szse.cn', 'www.sse.com.cn'} for r in reports)
    assert sum(item["pages"] for item in manifest) == 1765
    assert len(chunks) > 1000
    assert len(results) == 10
    assert len(retrieval_audit) == 10
    assert all(report['url'] in sources for report in reports)
    assert all(report['sha256'] in sources for report in manifest)
    assert len({row['chunk_id'] for row in chunks}) == len(chunks)
    assert all(row['embedding_backend'] in {'qwen', 'semantic'} for row in results)
    assert all(row['manual_verdict'] in {'correct', 'partial', 'wrong'} for row in results)
    assert all(row['ai_verdict'] == row['manual_verdict'] for row in results)
    assert all(row['independent_human_review'] == 'not_done' and row['human_verdict'] is None for row in results)
    assert sum(row['manual_verdict'] == 'correct' for row in results) >= 7, 'The requested 70% target has not been reached.'
    assert all(hashlib.sha256(row['answer'].encode()).hexdigest() == row['answer_sha256'] for row in results)
    assert all(row.get('reviewer') and row.get('verified_sources') for row in results)
    assert all(row['vector_recall'] and row['bm25_recall'] and row['final_chunks'] for row in results)
    assert all(item['stages']['final_chunks']['hits'] == item['stages']['final_chunks']['total'] for item in retrieval_audit)
    assert next(item for item in retrieval_audit if item['id'] == 'Q09')['stages']['fused_candidates']['hits'] == 7
    assert json.loads((ROOT / 'config/submission.json').read_text(encoding='utf-8'))['repository_url'] == 'https://github.com/leonardlee233/automotive-financial-rag'
    print('actual_verdicts=' + str(Counter(row['manual_verdict'] for row in results)))
    assert len(PdfReader(ROOT / "outputs" / "one_page_conclusion.pdf").pages) == 1
    with Image.open(ROOT / "outputs" / "streamlit_screenshot.png") as image:
        assert image.width >= 1200 and image.height >= 900
    assert not (ROOT / '.env').exists(), 'This delivery uses local inference and should not store credentials.'
    secret_pattern = re.compile(r"sk-[A-Za-z0-9_-]{20,}")
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in {".git", "work", "data"} for part in path.relative_to(ROOT).parts):
            continue
        if path.suffix.lower() not in {".py", ".md", ".txt", ".json", ".toml", ".example"}:
            continue
        assert not secret_pattern.search(path.read_text(encoding="utf-8", errors="ignore")), f"Possible API key in {path}"
    print("validated_reports=10")
    print("validated_pages=1765")
    print(f"validated_chunks={len(chunks)}")
    print("artifacts=ok")


if __name__ == "__main__":
    main()

