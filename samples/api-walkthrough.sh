#!/usr/bin/env bash
# Drives scenario S01 end to end through the HTTP API (the same calls the UI makes).
# Start the app first:  python dev.py run      then:  bash samples/api-walkthrough.sh
set -euo pipefail
BASE=${BASE:-http://127.0.0.1:8000}
H=(-H "Content-Type: application/json" -H "X-Reviewer-Id: demo-reviewer-01")
j() { python -c "import json,sys; d=json.load(sys.stdin); print(eval(sys.argv[1], {}, {'d': d}))" "$1"; }

curl -s -X POST "$BASE/demo/reset" >/dev/null
echo "1. Load S01 (intake + claims + plan v1 + preflight)"
V=$(curl -s -X POST "$BASE/demo/scenarios/S01/load" "${H[@]}")
P1=$(echo "$V" | j "d['plans'][-1]['plan_id']"); H1=$(echo "$V" | j "d['plans'][-1]['plan_hash']")
echo "   state: $(echo "$V" | j "d['case']['state']")   plan: $P1"

echo "2. Try to approve the blocked plan (refused by the server)"
curl -s -X POST "$BASE/plans/$P1/decisions" "${H[@]}" -d "{\"decision\":\"APPROVE\",\"plan_hash\":\"$H1\"}"; echo

echo "3. Modify: exclude the open web search -> plan v2 + fresh preflight"
R=$(curl -s -X POST "$BASE/plans/$P1/decisions" "${H[@]}" -d "{\"decision\":\"MODIFY\",\"plan_hash\":\"$H1\",\"reason\":\"No open websites\",\"restrictions\":{\"forbid_tools\":[\"unrestricted_web_search\"]}}")
P2=$(echo "$R" | j "d['plan']['plan_id']"); H2=$(echo "$R" | j "d['plan']['plan_hash']")
echo "   $P2 preflight: $(echo "$R" | j "d['preflight']['status']")"

echo "4. Approve v2 (bound to its hash)"
curl -s -X POST "$BASE/plans/$P2/decisions" "${H[@]}" -d "{\"decision\":\"APPROVE\",\"plan_hash\":\"$H2\"}" >/dev/null

echo "5. Red team: a forbidden call straight to the gate"
curl -s -X POST "$BASE/cases/CASE-DEMO-001/redteam/attempt-tool" "${H[@]}" -d '{"tool_id":"unrestricted_web_search","arguments":{"query":"x"},"step_id":"S1"}' | j "d['receipt']['tool_call_status'] + ' / MCP invocations: ' + str(d['mcp_invocations'])"

echo "6. Run the approved checks"
X=$(curl -s -X POST "$BASE/cases/CASE-DEMO-001/execute" "${H[@]}")
echo "   verdicts: $(echo "$X" | j "[(f['claim_id'], f['verdict']) for f in d['findings']]")"
P3=$(echo "$X" | j "d['replan']['plan']['plan_id']"); H3=$(echo "$X" | j "d['replan']['plan']['plan_hash']")
echo "   agent asks for more scope: $P3"

echo "7. Approve v3 and run it"
curl -s -X POST "$BASE/plans/$P3/decisions" "${H[@]}" -d "{\"decision\":\"APPROVE\",\"plan_hash\":\"$H3\"}" >/dev/null
curl -s -X POST "$BASE/cases/CASE-DEMO-001/execute" "${H[@]}" >/dev/null

echo "8. Sign off"
curl -s -X POST "$BASE/cases/CASE-DEMO-001/final-review" "${H[@]}" -d '{"decision":"SIGN_OFF","note":"Reviewed"}' | j "d['state']"

echo "9. Evidence pack + verification"
curl -s "$BASE/cases/CASE-DEMO-001/pack" "${H[@]}" > /tmp/S01-pack.json
curl -s -X POST "$BASE/packs/verify" "${H[@]}" --data-binary @/tmp/S01-pack.json | j "d"
echo "   report: $BASE/cases/CASE-DEMO-001/pack.md"
