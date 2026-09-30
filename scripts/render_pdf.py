from __future__ import annotations

import argparse
from pathlib import Path

import pypdfium2 as pdfium
from pypdf import PdfReader


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--scale", type=float, default=2.0)
    args = parser.parse_args()
    reader = PdfReader(args.pdf)
    print(f"pages={len(reader.pages)}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    pdf = pdfium.PdfDocument(str(args.pdf))
    for index in range(len(pdf)):
        image = pdf[index].render(scale=args.scale).to_pil()
        path = args.output.with_name(f"{args.output.stem}-{index + 1}.png")
        image.save(path)
        print(path)


if __name__ == "__main__":
    main()

