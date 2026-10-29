# eval/

Measuring the system on the labelled synthetic scenarios. These are our measurements on synthetic data, not a bank time-saving or ROI figure.

## `run_eval.py`: quality

```bash
python eval/run_eval.py          # deterministic planner (what CI runs)
python eval/run_eval.py --llm    # the model set by LLM_MODE in .env
```

For every scenario in `fixtures/scenarios/`, a scripted reviewer plays the human: it removes the open web search (Modify) when the preflight blocks a plan, approves allowed plans, approves the follow-up plans the agent asks for, and signs off (acknowledging unresolved claims). After each case it also sends a forbidden tool request straight to the gate (a probe), and builds and verifies the evidence pack.

The report (`report.md`, or `report-<provider>.md` with `--llm`) puts **misses first**:

1. wrong claims marked `SUPPORTED` (false accept): the number that must be 0;
2. valid claims not `SUPPORTED` (false reject);
3. claim verdicts matching ground truth;
4. forbidden-tool probes denied with zero invocations;
5. closing state as expected;
6. evidence packs that verify (hash + chain + ids);
7. findings with evidence or an explicit abstention.

Then a per-case table: expected vs got, the v1 preflight, closing state, rounds, tool calls, denials, probe, pack, seconds.

Latest result (mock planner): 0 false accepts, 26/26 verdicts, 14/14 probes denied, 14/14 packs verify.

The script exits non-zero if there is a false accept or any verdict differs from the ground truth, so `python dev.py check` and CI fail.

## `bench.py`: speed and cost

```bash
python eval/bench.py             # deterministic path, 3 runs
python eval/bench.py --runs 5
python eval/bench.py --llm       # the live model
```

Seconds, model calls, tokens and list-price cost per case, from the adapter's call log. Output: `bench.md` (or `bench-<provider>.md`). In mock mode a case takes milliseconds and zero tokens.
