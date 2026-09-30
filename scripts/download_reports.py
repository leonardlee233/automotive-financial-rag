from __future__ import annotations

import argparse
import gzip
import json
import sys
import urllib.request
from pathlib import Path

from pypdf import PdfReader

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import ROOT, read_json, sha256_file, write_json


def download(url: str, destination: Path) -> None:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36",
            "Referer": "https://www.sse.com.cn/" if "sse.com.cn" in url else "https://www.cninfo.com.cn/",
            "Accept": "application/pdf,application/octet-stream;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        data = response.read()
    if data.startswith(b"\x1f\x8b"):
        data = gzip.decompress(data)
    pdf_at = data.find(b"%PDF")
    if pdf_at < 0:
        preview = data[:120].decode("utf-8", errors="replace")
        raise ValueError(f"Downloaded content is not a PDF: {url}; prefix={preview!r}")
    data = data[pdf_at:]
    destination.write_bytes(data)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    reports = read_json(ROOT / "config" / "reports.json")
    raw_dir = ROOT / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for report in reports:
        path = raw_dir / f"{report['stock_code']}_{report['company']}_2026H1.pdf"
        if args.force or not path.exists():
            print(f"Downloading {report['company']} ...", flush=True)
            download(report["url"], path)
        reader = PdfReader(path)
        item = dict(report)
        item.update({"file": path.name, "bytes": path.stat().st_size, "pages": len(reader.pages), "sha256": sha256_file(path)})
        manifest.append(item)
        print(f"OK {report['company']}: {item['pages']} pages, {item['bytes']:,} bytes", flush=True)
    write_json(ROOT / "data" / "processed" / "download_manifest.json", manifest)
    print(f"Validated {len(manifest)} official full-report PDFs.")


if __name__ == "__main__":
    main()

