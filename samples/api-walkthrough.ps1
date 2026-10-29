# Drives scenario S01 end to end through the HTTP API (the same calls the UI makes).
# Start the app first:  python dev.py run      then (PowerShell):  .\samples\api-walkthrough.ps1
$Base = if ($env:BASE) { $env:BASE } else { "http://127.0.0.1:8000" }
$H = @{ "X-Reviewer-Id" = "demo-reviewer-01" }
function Post($path, $body) {
  $json = if ($body) { $body | ConvertTo-Json -Depth 10 } else { "{}" }
  Invoke-RestMethod -Method Post -Uri "$Base$path" -Headers $H -ContentType "application/json" -Body $json
}

Invoke-RestMethod -Method Post -Uri "$Base/demo/reset" | Out-Null
"1. Load S01 (intake + claims + plan v1 + preflight)"
$v = Post "/demo/scenarios/S01/load"
$p1 = $v.plans[-1]
"   state: $($v.case.state)   plan: $($p1.plan_id)"

"2. Try to approve the blocked plan (refused by the server)"
try { Post "/plans/$($p1.plan_id)/decisions" @{ decision = "APPROVE"; plan_hash = $p1.plan_hash } | Out-Null }
catch { "   refused: $($_.ErrorDetails.Message)" }

"3. Modify: exclude the open web search -> plan v2 + fresh preflight"
$r = Post "/plans/$($p1.plan_id)/decisions" @{ decision = "MODIFY"; plan_hash = $p1.plan_hash; reason = "No open websites"; restrictions = @{ forbid_tools = @("unrestricted_web_search") } }
"   $($r.plan.plan_id) preflight: $($r.preflight.status)"

"4. Approve v2 (bound to its hash)"
Post "/plans/$($r.plan.plan_id)/decisions" @{ decision = "APPROVE"; plan_hash = $r.plan.plan_hash } | Out-Null

"5. Red team: a forbidden call straight to the gate"
$t = Post "/cases/CASE-DEMO-001/redteam/attempt-tool" @{ tool_id = "unrestricted_web_search"; arguments = @{ query = "x" }; step_id = "S1" }
"   $($t.receipt.tool_call_status): $($t.receipt.denial_reasons[0])"

"6. Run the approved checks"
$x = Post "/cases/CASE-DEMO-001/execute"
$x.findings | ForEach-Object { "   $($_.claim_id): $($_.verdict)" }
"   agent asks for more scope: $($x.replan.plan.plan_id)"

"7. Approve v3 and run it"
Post "/plans/$($x.replan.plan.plan_id)/decisions" @{ decision = "APPROVE"; plan_hash = $x.replan.plan.plan_hash } | Out-Null
Post "/cases/CASE-DEMO-001/execute" | Out-Null

"8. Sign off"
(Post "/cases/CASE-DEMO-001/final-review" @{ decision = "SIGN_OFF"; note = "Reviewed" }).state

"9. Evidence pack + verification"
$pack = Invoke-RestMethod -Uri "$Base/cases/CASE-DEMO-001/pack" -Headers $H
$check = Invoke-RestMethod -Method Post -Uri "$Base/packs/verify" -Headers $H -ContentType "application/json" -Body ($pack | ConvertTo-Json -Depth 30)
"   pack ok: $($check.ok)   report: $Base/cases/CASE-DEMO-001/pack.md"
