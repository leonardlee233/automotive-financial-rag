"""Download public model weights/runtime; no credentials or remote inference."""
from pathlib import Path
import re
import zipfile
import requests
import sys

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "work" / "models"


def download(url, path):
    if path.exists():
        print(f"Already present: {path.name}", flush=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".part")
    with requests.get(url, stream=True, timeout=(30, 180)) as response:
        response.raise_for_status()
        count = 0
        with temp.open("wb") as out:
            for block in response.iter_content(4 * 1024 * 1024):
                out.write(block)
                count += len(block)
                if count % (128 * 1024 * 1024) < len(block):
                    print(f"{path.name}: {count // 1024**2} MiB", flush=True)
    temp.replace(path)


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    if "--embedding" in sys.argv:
        from huggingface_hub import snapshot_download
        snapshot_download("Qwen/Qwen3-Embedding-0.6B", local_dir=DEST / "Qwen3-Embedding-0.6B",
                          ignore_patterns=["*.onnx", "onnx/*", "*.bin"])
        return
    if "--light-embedding" in sys.argv:
        from huggingface_hub import snapshot_download
        snapshot_download("BAAI/bge-small-zh-v1.5", local_dir=DEST / "bge-small-zh-v1.5",
                          ignore_patterns=["*.onnx", "onnx/*", "*.bin"])
        return
    release = "b9380"
    page = requests.get(f"https://github.com/ggml-org/llama.cpp/releases/expanded_assets/{release}", timeout=30)
    page.raise_for_status()
    links = re.findall(r'href="([^"]+\.zip)"', page.text)
    matching = [x for x in links if "win-cpu-x64" in x]
    if not matching:
        raise RuntimeError(f"No CPU asset found: {links}")
    runtime = DEST / "llama-cpu.zip"
    download("https://github.com" + matching[0], runtime)
    target = DEST / "llama-cpu"
    target.mkdir(exist_ok=True)
    with zipfile.ZipFile(runtime) as archive:
        for name in archive.namelist():
            if not (target / name).resolve().is_relative_to(target.resolve()):
                raise ValueError("Unsafe archive member")
        archive.extractall(target)
    name = "Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
    download(f"https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF/resolve/main/{name}", DEST / name)
    print("Local model and runtime ready.", flush=True)


if __name__ == "__main__":
    main()
