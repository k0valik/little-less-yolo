#!/usr/bin/env python3
"""Inspect the GAIA validation set to pick easy / hard pilot tasks.

Run after accepting the gated dataset terms on huggingface.co.

    python benchmarks/gaia_inspect.py
        → prints L1/L2/L3 counts, picks 4 pilot tasks (2 easy, 2 hard),
          favors web-research tasks (no file_name), writes
          benchmarks/gaia_runs/_pilot_picks.json

Heuristic: prefer tasks where the question contains an obvious web-research
hook (Wikipedia, arxiv, search, year, name) and no attachment. We want the
pilot to exercise BrowserNavigate / BrowserExtract / EvidenceAdd before we
spend a turn iterating on attachment handling.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from gaia import _load_split  # noqa: E402

WEB_HOOKS = re.compile(
    r"\b(wikipedia|arxiv|paper|published|article|website|google scholar|youtube|"
    r"according to|in the article|musical|painter|author|olympics|Nobel|date of)\b",
    re.IGNORECASE,
)


def _looks_web(task: dict) -> bool:
    if (task.get("file_name") or "").strip():
        return False  # has attachment — skip for pilot
    q = task.get("Question") or ""
    return bool(WEB_HOOKS.search(q))


def main():
    records, root = _load_split("2023", None, "validation")
    by_level: dict[int, list[dict]] = {1: [], 2: [], 3: []}
    for r in records:
        lvl = int(r.get("Level") or 0)
        by_level.setdefault(lvl, []).append(r)
    print(f"validation: {len(records)} tasks @ {root}")
    for lvl, xs in sorted(by_level.items()):
        n_attach = sum(1 for x in xs if (x.get("file_name") or "").strip())
        print(f"  L{lvl}: {len(xs)} tasks  ({n_attach} with attachments)")

    # Pick 2 L1 (easy) + 2 L2 (hard) web-research tasks.
    picks: list[dict] = []
    for lvl, want in [(1, 2), (2, 2)]:
        candidates = [r for r in by_level[lvl] if _looks_web(r)]
        if len(candidates) < want:
            candidates = [r for r in by_level[lvl] if not (r.get("file_name") or "").strip()]
        # Prefer shorter questions for L1 (fewer unknowns), longer for L2 (multi-hop).
        candidates.sort(key=lambda r: len(r.get("Question") or ""))
        if lvl == 2:
            candidates = list(reversed(candidates))
        picks.extend(candidates[:want])

    print("\npicks:")
    for p in picks:
        q = (p.get("Question") or "").replace("\n", " ")
        if len(q) > 120:
            q = q[:117] + "..."
        print(f"  L{p.get('Level')}  {p['task_id']}  {q!r}")
        print(f"        gold: {p.get('Final answer')!r}")

    out = Path(__file__).parent / "gaia_runs"
    out.mkdir(parents=True, exist_ok=True)
    (out / "_pilot_picks.json").write_text(json.dumps(
        [{"task_id": p["task_id"],
          "level": p.get("Level"),
          "question": p.get("Question"),
          "gold": p.get("Final answer")} for p in picks],
        indent=2,
    ))
    print(f"\nwrote {out / '_pilot_picks.json'}")
    print("\nrun pilot:")
    print(f"  benchmarks/gaia_pilot.sh {' '.join(p['task_id'] for p in picks)}")


if __name__ == "__main__":
    main()
