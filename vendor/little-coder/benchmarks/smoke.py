#!/usr/bin/env python3
"""Quick smoke test: send one prompt through pi RPC and print the result.

Usage:
    python benchmarks/smoke.py "list the files in this directory"
    python benchmarks/smoke.py --model llamacpp/qwen3.5-9b "hello"
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rpc_client import PiRpc  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("message", nargs="+")
    ap.add_argument("--model", default="llamacpp/qwen3.6-35b-a3b")
    ap.add_argument("--cwd", default=str(Path.cwd()))
    ap.add_argument("--timeout", type=int, default=300)
    args = ap.parse_args()

    msg = " ".join(args.message)
    print(f"[smoke] model={args.model}", file=sys.stderr)
    print(f"[smoke] cwd={args.cwd}", file=sys.stderr)
    print(f"[smoke] prompt: {msg}", file=sys.stderr)
    print(file=sys.stderr)

    with PiRpc(model=args.model, cwd=args.cwd) as rpc:
        r = rpc.prompt_and_collect(msg, timeout=args.timeout)
        print("=== assistant text ===")
        print(r.assistant_text or "(empty)")
        print()
        print(f"=== tool calls ({len(r.tool_calls)}) ===")
        for tc in r.tool_calls:
            preview = (tc.get("result_text", "") or "")[:200]
            err = "!" if tc.get("is_error") else " "
            print(f"{err} {tc['name']}({tc.get('args', {})})")
            print(f"    -> {preview}")
        print()
        print(f"=== meta: turns={r.turn_count}, compactions={r.compaction_events}, ended={r.agent_ended}")


if __name__ == "__main__":
    main()
