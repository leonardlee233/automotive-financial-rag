"""Apply explicit, hash-bound review records; never infer grades from question ids."""
import argparse
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import read_jsonl, read_json, write_jsonl


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path)
    parser.add_argument("review", type=Path)
    args = parser.parse_args()
    rows = read_jsonl(args.results)
    reviews = read_json(args.review)
    for row in rows:
        review = reviews[row["id"]]
        digest = hashlib.sha256(row["answer"].encode()).hexdigest()
        if digest != review["answer_sha256"]:
            raise ValueError(f"Stale review for {row['id']}; rereview the actual new answer")
        if review["verdict"] not in {"correct", "partial", "wrong"}:
            raise ValueError("Invalid verdict")
        row.update(manual_verdict=review["verdict"], reason=review["reason"],
                   error_type=review["error_type"], reviewer=review["reviewer"],
                   verified_sources=review["sources"])
        # `manual_verdict` is retained for compatibility with earlier runs;
        # this review was performed by an AI assistant, not an independent human.
        row["ai_verdict"] = review["verdict"]
        row["review_method"] = "AI-assisted source comparison"
        row["independent_human_review"] = "not_done"
        row["human_verdict"] = None
        row["review_short"] = review.get("short", review["reason"])
    write_jsonl(args.results, rows)


if __name__ == "__main__":
    main()
