# Samples

All data here is synthetic.

## Inputs
- **`S01-input-case.json`**: what the bank's AI agent hands to Agent Assurance: the finding (*"NOVA Logistics SRL is currently involved in an ongoing legal dispute (case C-001)."*), the subject (company id `RO-DEMO-48219370`), the origin system (AI Act class `UNCONFIRMED`), the purpose and the attached evidence (a 2024 article). The demo loads it for you; it's here so you can see the input shape.
- **`custom-case-request.json`**: a case created by an employee (`origin: HUMAN`) that reuses scenario S05's synthetic sources. Post it yourself:

```bash
curl -X POST http://127.0.0.1:8000/cases -H "Content-Type: application/json" -H "X-Reviewer-Id: demo-reviewer-01" -d @samples/custom-case-request.json
curl -X POST http://127.0.0.1:8000/cases/CASE-MY-001/assess -H "X-Reviewer-Id: demo-reviewer-01"
curl -X POST http://127.0.0.1:8000/cases/CASE-MY-001/plans  -H "Content-Type: application/json" -H "X-Reviewer-Id: demo-reviewer-01" -d "{}"
```
Then approve the returned plan (`POST /plans/{plan_id}/decisions` with `{"decision":"APPROVE","plan_hash":"..."}`) and run `POST /cases/CASE-MY-001/execute`. Expected: the claim "revenue fell 20%" is `SUPPORTED`, computed in code from the 2024 and 2025 filings.

The tools only know the synthetic records in `fixtures/scenarios/*.json` (`tool_data`), so a custom case needs a `scenario_id` whose data it can use; otherwise every lookup returns "no record" and the claim ends `INSUFFICIENT_EVIDENCE`, never `SUPPORTED`.

## Walkthrough scripts
Start the app (`python dev.py run`), then:
- macOS / Linux / Git Bash: `bash samples/api-walkthrough.sh`
- Windows PowerShell: `.\samples\api-walkthrough.ps1` (if scripts are blocked: `powershell -ExecutionPolicy Bypass -File samples\api-walkthrough.ps1`)

Both run S01: load → try to approve the blocked plan (refused) → modify → approve v2 → a forbidden call (denied, zero invocations) → run → approve v3 → run → sign off → download and verify the pack.

## Outputs of that run
- **`S01-evidence-pack.json`**: plans v1–v3 with fingerprints, preflight results, human decisions, every tool receipt (incl. the denied one), evidence with SHA-256 of each record, verdicts, the full event log, `ledger_verification` and `pack_sha256`. Check it with `POST /packs/verify`.
- **`S01-report.md`**: the same pack, human-readable.
- **`S01-ledger.jsonl`**: the raw event log. Each line's `previous_event_hash` is the previous line's `event_hash`; `POST /ledger/verify` (body: the file as text) names the first broken entry if anything was edited.
