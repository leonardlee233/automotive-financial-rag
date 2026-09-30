from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs" / "automotive_financial_rag_assignment.zip"

EXCLUDED_DIRS = {".git", ".pytest_cache", "__pycache__", "work", ".venv", "models"}


def include(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    if any(part in EXCLUDED_DIRS for part in relative.parts):
        return False
    if relative == Path("outputs") / OUTPUT.name:
        return False
    if relative.parts[:2] == ("data", "raw") and path.suffix.lower() == ".pdf":
        return False
    if relative.parts[:2] == ("data", "processed") and path.suffix.lower() == ".jsonl":
        return False
    if relative.parts[:2] == ("data", "index"):
        return path.name == ".gitkeep"
    if (path.name.startswith(".env") and path.name != ".env.example") or path.suffix.lower() in {".pyc", ".pyo", ".gguf"}:
        return False
    return True


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(OUTPUT, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(ROOT.rglob("*")):
            if path.is_file() and include(path):
                archive.write(path, path.relative_to(ROOT))
    print(OUTPUT)
    print(f"bytes={OUTPUT.stat().st_size}")


if __name__ == "__main__":
    main()

