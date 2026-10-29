"""Bench: seconds, model calls, tokens and list-price cost per case over N runs (vault: "Agent speed and
token cost", section 6). Mock mode measures the deterministic path (zero tokens); LLM_MODE=bedrock in .env
plus --llm measures the live model. Nothing here is a bank figure: synthetic cases, our measurement.

    python eval/bench.py               # mock planner, 3 runs
    python eval/bench.py --runs 5
    python eval/bench.py --llm         # LLM_MODE from .env (needs the Bedrock key)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.llm.adapter import LLM, percentile  # noqa: E402
from backend.workflow.orchestrator import Orchestrator  # noqa: E402
from run_eval import run_case  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--llm", action="store_true", help="use LLM_MODE from .env instead of the mock planner")
    ap.add_argument("--out", default=None, help="output path (default eval/bench.md, or eval/bench-<provider>.md with --llm)")
    args = ap.parse_args()
    per_case: dict[str, dict] = {}
    label = None
    provider = None
    totals = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0, "cost_estimate_usd": 0.0}
    for _ in range(args.runs):
        orch = Orchestrator(llm=LLM() if args.llm else LLM("mock"))
        label = label or orch.llm.label
        provider = provider or orch.llm.mode
        for sid in sorted(orch.mcp.scenarios):
            before = len(orch.llm.calls_log)
            row = run_case(orch, sid)
            calls = [r for r in orch.llm.calls_log[before:] if "task" in r]
            c = per_case.setdefault(sid, {"title": row["title"], "seconds": [], "calls": [], "input_tokens": 0, "output_tokens": 0,
                                          "cache_read_input_tokens": 0, "cost_estimate_usd": 0.0, "ok": 0, "tool_calls": [], "denied": []})
            c["seconds"].append(row["seconds"])
            c["calls"].append(len(calls))
            c["tool_calls"].append(row["tool_calls"])
            c["denied"].append(row["denied"])
            c["ok"] += int(row["expected"] == row["got"] and row["closure"] == row["closure_expected"])
            for r in calls:
                for k in ("input_tokens", "output_tokens", "cache_read_input_tokens"):
                    c[k] += r[k]
                    totals[k] += r[k]
                c["cost_estimate_usd"] = round(c["cost_estimate_usd"] + (r["cost_estimate_usd"] or 0), 8)
                totals["cost_estimate_usd"] = round(totals["cost_estimate_usd"] + (r["cost_estimate_usd"] or 0), 8)
                totals["calls"] += 1
    n = args.runs
    lines = [
        "# Bench (synthetic scenarios, our measurement)", "",
        f"Planner: **{label}** · {n} runs · {len(per_case)} cases · list prices, Bedrock may differ", "",
        "| Case | Correct | Agent s p50 | Agent s p95 | Model calls/run | Input tok/run | Output tok/run | Cache read/run | Cost USD/run | Tool calls | Denied |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for sid, c in per_case.items():
        lines.append(
            f"| {sid} {c['title']} | {c['ok']}/{n} | {percentile(c['seconds'], 50):.3f} | {percentile(c['seconds'], 95):.3f} | "
            f"{sum(c['calls']) / n:.1f} | {c['input_tokens'] / n:.0f} | {c['output_tokens'] / n:.0f} | {c['cache_read_input_tokens'] / n:.0f} | "
            f"{c['cost_estimate_usd'] / n:.5f} | {sum(c['tool_calls']) / n:.1f} | {sum(c['denied']) / n:.1f} |")
    all_seconds = [s for c in per_case.values() for s in c["seconds"]]
    lines += ["",
              f"**Per case, all runs:** agent seconds p50 {percentile(all_seconds, 50):.3f}, p95 {percentile(all_seconds, 95):.3f}; "
              f"model calls {totals['calls'] / n / max(1, len(per_case)):.1f}; input tokens {totals['input_tokens'] / n / max(1, len(per_case)):.0f}; "
              f"output tokens {totals['output_tokens'] / n / max(1, len(per_case)):.0f}; cache hit share "
              f"{(totals['cache_read_input_tokens'] / (totals['input_tokens'] + totals['cache_read_input_tokens'])) if (totals['input_tokens'] + totals['cache_read_input_tokens']) else 0:.0%}; "
              f"cost per case USD {totals['cost_estimate_usd'] / n / max(1, len(per_case)):.5f} (list price, estimate).",
              "",
              "Spec estimates to beat (vault, 'Agent speed and token cost' §2–3): about 21,500 input and 3,800 output tokens, about 11 model calls, "
              "about 15 s agent time per case with the live model; under 2 s on the deterministic path. Human steps are not agent time.",
              "", "_No number from this table goes on a slide without the words: synthetic cases, our measurement, list price._", ""]
    report = "\n".join(lines)
    default_name = f"bench-{provider}.md" if args.llm else "bench.md"
    (Path(args.out) if args.out else Path(__file__).resolve().parent / default_name).write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
