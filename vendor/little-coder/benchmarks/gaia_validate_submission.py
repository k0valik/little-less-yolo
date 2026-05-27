#!/usr/bin/env python3
"""Validate a GAIA submission.jsonl before uploading to the leaderboard.

Mirrors the server-side checks in
huggingface.co/spaces/gaia-benchmark/leaderboard/blob/main/app.py:add_new_eval()
so we don't get rejected after a 15h test run:

  - file is JSONL, every line valid JSON
  - every line has 'task_id' (string) and 'model_answer' (string) keys
  - no duplicate task_ids
  - test split: exactly 93 L1 / 159 L2 / 49 L3 tasks (301 total)
  - validation split: exactly 53 L1 / 86 L2 / 26 L3 tasks (165 total)

When --gold is passed (validation only), also computes the local expected
score using the GAIA-faithful scorer.

Usage:
    python benchmarks/gaia_validate_submission.py path/to/submission.jsonl
    python benchmarks/gaia_validate_submission.py path/to/submission.jsonl \\
        --split validation --score
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from gaia_scorer import score  # noqa: E402

REQUIRED_LEVEL_COUNTS = {
    "test": {1: 93, 2: 159, 3: 49},
    "validation": {1: 53, 2: 86, 3: 26},
}


def _load_submission(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open() as f:
        for ln, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                sys.exit(f"line {ln}: invalid JSON — {e}")
    return rows


def _load_gold(split: str, year: str = "2023") -> dict[str, dict]:
    """Return {task_id: {Level, Final answer}} for the requested split."""
    sys.path.insert(0, str(Path(__file__).parent))
    from gaia import _load_split  # noqa: E402
    records, _ = _load_split(year, None, split)
    return {r["task_id"]: r for r in records}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("submission", type=Path)
    ap.add_argument("--split", choices=("validation", "test"), default="test")
    ap.add_argument("--year", default="2023")
    ap.add_argument("--score", action="store_true",
                    help="On validation, compute expected leaderboard score")
    args = ap.parse_args()

    if not args.submission.exists():
        sys.exit(f"missing: {args.submission}")
    rows = _load_submission(args.submission)
    print(f"loaded {len(rows)} rows from {args.submission}")

    fail = False

    # 1. schema
    seen_ids: set[str] = set()
    for i, r in enumerate(rows, 1):
        if not isinstance(r.get("task_id"), str) or not r["task_id"]:
            print(f"  row {i}: missing/empty task_id"); fail = True
        if "model_answer" not in r:
            print(f"  row {i}: missing model_answer"); fail = True
        elif not isinstance(r["model_answer"], str):
            print(f"  row {i}: model_answer must be a string"); fail = True
        tid = r.get("task_id", "")
        if tid in seen_ids:
            print(f"  row {i}: duplicate task_id {tid}"); fail = True
        seen_ids.add(tid)

    # 2. coverage vs gold
    gold = _load_gold(args.split, args.year)
    expected_ids = set(gold.keys())
    submitted_ids = {r.get("task_id", "") for r in rows}
    missing = expected_ids - submitted_ids
    extra = submitted_ids - expected_ids
    if missing:
        print(f"  MISSING {len(missing)} task_ids (e.g. {sorted(missing)[:3]})"); fail = True
    if extra:
        print(f"  UNKNOWN {len(extra)} task_ids not in {args.split} gold (e.g. {sorted(extra)[:3]})"); fail = True

    # 3. level counts
    counts = {1: 0, 2: 0, 3: 0}
    for r in rows:
        g = gold.get(r.get("task_id"))
        if not g:
            continue
        try:
            lvl = int(g.get("Level") or 0)
        except (TypeError, ValueError):
            continue
        if lvl in counts:
            counts[lvl] += 1
    expected = REQUIRED_LEVEL_COUNTS[args.split]
    print(f"  level counts: L1={counts[1]} L2={counts[2]} L3={counts[3]}  (expected: L1={expected[1]} L2={expected[2]} L3={expected[3]})")
    if counts != expected:
        print("  LEVEL COUNTS WRONG — leaderboard will reject"); fail = True

    # 4. empty answers (warning only — server does NOT reject these but they hurt the score)
    n_empty = sum(1 for r in rows if not (r.get("model_answer") or "").strip())
    if n_empty:
        print(f"  warning: {n_empty}/{len(rows)} rows have empty model_answer")

    # 5. local score (validation only)
    if args.score and args.split == "validation":
        n_correct = 0
        per_level = {1: [0, 0], 2: [0, 0], 3: [0, 0]}
        for r in rows:
            g = gold.get(r.get("task_id"))
            if not g:
                continue
            try:
                lvl = int(g.get("Level") or 0)
            except (TypeError, ValueError):
                lvl = 0
            ok, _ = score(r.get("model_answer", ""), g.get("Final answer", ""))
            if lvl in per_level:
                per_level[lvl][1] += 1
                if ok:
                    per_level[lvl][0] += 1
            if ok:
                n_correct += 1
        pct = (n_correct / len(rows) * 100) if rows else 0.0
        print(f"\n  local expected score: {n_correct}/{len(rows)} = {pct:.2f}%")
        for lvl, (c, n) in per_level.items():
            if n:
                print(f"    L{lvl}: {c}/{n} = {(c/n*100):.2f}%")

    print()
    if fail:
        sys.exit("REJECTED — fix the issues above before uploading.")
    print("VALID — submission.jsonl ready to upload.")


if __name__ == "__main__":
    main()
