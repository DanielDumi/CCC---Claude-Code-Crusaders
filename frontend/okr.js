"use strict";
/* Demos by job to be done, mapped to OKRs.
   A reviewer hires Agent Assurance for five jobs. Each job has one objective and a few key results. A key result is a
   task that ticks itself from the case record app.js already fetched (claims, plans, preflights, approvals, receipts,
   findings, events) or from what you did in the UI (safeguard tests, log checks, pack download).
   This file never calls the API and never changes a verdict, a preflight result or a decision: it only reads and renders.
   It owns the shell around the case: sidebar, top bar, overview, job pages, the side panel of a case, and the hash
   routes (#/ · #/job/J1 · #/case/S01/J1) so the browser's back button works. The session scorecard lives in
   sessionStorage so a reload keeps it; "Reset demo" clears it. */

const OKR = (() => {
  const $ = (id) => document.getElementById(id);
  const h = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  /* icons: exact paths from @untitledui/icons (Untitled UI Pro kit, line style, 24 viewBox, 2px stroke) */
  const PATH = {"home":["M9 21v-7.4c0-.56 0-.84.109-1.054a1 1 0 0 1 .437-.437C9.76 12 10.04 12 10.6 12h2.8c.56 0 .84 0 1.054.109a1 1 0 0 1 .437.437C15 12.76 15 13.04 15 13.6V21M2 9.5l9.04-6.78c.344-.258.516-.387.705-.437a1 1 0 0 1 .51 0c.189.05.36.179.705.437L22 9.5M4 8v9.8c0 1.12 0 1.68.218 2.108a2 2 0 0 0 .874.874C5.52 21 6.08 21 7.2 21h9.6c1.12 0 1.68 0 2.108-.218a2 2 0 0 0 .874-.874C20 19.48 20 18.92 20 17.8V8l-6.08-4.56c-.688-.516-1.033-.775-1.41-.874a2 2 0 0 0-1.02 0c-.377.1-.722.358-1.41.874L4 8Z"],"search":["M14 11H8m2 4H8m8-8H8m12 3.5V6.8c0-1.68 0-2.52-.327-3.162a3 3 0 0 0-1.311-1.311C17.72 2 16.88 2 15.2 2H8.8c-1.68 0-2.52 0-3.162.327a3 3 0 0 0-1.311 1.311C4 4.28 4 5.12 4 6.8v10.4c0 1.68 0 2.52.327 3.162a3 3 0 0 0 1.311 1.311C6.28 22 7.12 22 8.8 22h2.7M22 22l-1.5-1.5m1-2.5a3.5 3.5 0 1 1-7 0 3.5 3.5 0 0 1 7 0Z"],"clipboard":["M16 4c.93 0 1.395 0 1.776.102a3 3 0 0 1 2.122 2.122C20 6.605 20 7.07 20 8v9.2c0 1.68 0 2.52-.327 3.162a3 3 0 0 1-1.311 1.311C17.72 22 16.88 22 15.2 22H8.8c-1.68 0-2.52 0-3.162-.327a3 3 0 0 1-1.311-1.311C4 19.72 4 18.88 4 17.2V8c0-.93 0-1.395.102-1.776a3 3 0 0 1 2.122-2.122C6.605 4 7.07 4 8 4m1 11 2 2 4.5-4.5M9.6 6h4.8c.56 0 .84 0 1.054-.109a1 1 0 0 0 .437-.437C16 5.24 16 4.96 16 4.4v-.8c0-.56 0-.84-.109-1.054a1 1 0 0 0-.437-.437C15.24 2 14.96 2 14.4 2H9.6c-.56 0-.84 0-1.054.109a1 1 0 0 0-.437.437C8 2.76 8 3.04 8 3.6v.8c0 .56 0 .84.109 1.054a1 1 0 0 0 .437.437C8.76 6 9.04 6 9.6 6Z"],"lock":["M17 10V8A5 5 0 0 0 7 8v2m5 4.5v2M8.8 21h6.4c1.68 0 2.52 0 3.162-.327a3 3 0 0 0 1.311-1.311C20 18.72 20 17.88 20 16.2v-1.4c0-1.68 0-2.52-.327-3.162a3 3 0 0 0-1.311-1.311C17.72 10 16.88 10 15.2 10H8.8c-1.68 0-2.52 0-3.162.327a3 3 0 0 0-1.311 1.311C4 12.28 4 13.12 4 14.8v1.4c0 1.68 0 2.52.327 3.162a3 3 0 0 0 1.311 1.311C6.28 21 7.12 21 8.8 21Z"],"shield":["m8.809 3.197 2.63-.986c.207-.078.311-.117.418-.133a1 1 0 0 1 .286 0c.107.016.21.055.419.133l5.362 2.01c.748.28 1.123.421 1.398.664a2 2 0 0 1 .547.79c.131.343.131.743.131 1.542V12c0 .72-.115 1.412-.318 2.07m-2.06 3.555c-1.686 1.96-3.834 3.354-4.922 3.989-.223.13-.334.194-.49.228a1.137 1.137 0 0 1-.42 0c-.156-.034-.267-.098-.488-.227C9.354 20.478 4 16.908 4 12V5.776c0-.467.29-.885.727-1.049M3 3l18 18"],"archive":["M4 7.997a2.295 2.295 0 0 1-.39-.035A2 2 0 0 1 2.038 6.39C2 6.197 2 5.965 2 5.5s0-.697.038-.89A2 2 0 0 1 3.61 3.038C3.803 3 4.035 3 4.5 3h15c.465 0 .697 0 .89.038a2 2 0 0 1 1.572 1.572c.038.193.038.425.038.89s0 .697-.038.89a2 2 0 0 1-1.572 1.572c-.107.02-.226.03-.39.035M10 13h4M4 8h16v8.2c0 1.68 0 2.52-.327 3.162a3 3 0 0 1-1.311 1.311C17.72 21 16.88 21 15.2 21H8.8c-1.68 0-2.52 0-3.162-.327a3 3 0 0 1-1.311-1.311C4 18.72 4 17.88 4 16.2V8Z"],"check":["M20 6 9 17l-5-5"],"right":["m9 18 6-6-6-6"],"play":["M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10Z","M9.5 8.965c0-.477 0-.716.1-.849a.5.5 0 0 1 .364-.199c.166-.012.367.117.769.375l4.72 3.035c.349.224.523.336.583.478a.5.5 0 0 1 0 .39c-.06.142-.234.254-.583.478l-4.72 3.035c-.402.258-.603.387-.769.375a.5.5 0 0 1-.364-.2c-.1-.132-.1-.371-.1-.848v-6.07Z"],"reset":["M2 10s2.005-2.732 3.634-4.362A9 9 0 1 1 12 21a9.004 9.004 0 0 1-8.648-6.5M2 10V4m0 6h6"],"close":["M18 6 6 18M6 6l12 12"],"next":["M5 12h14m0 0-7-7m7 7-7 7"],"pause":["M9.5 15V9m5 6V9m7.5 3c0 5.523-4.477 10-10 10S2 17.523 2 12 6.477 2 12 2s10 4.477 10 10Z"],"ai":["M4.5 22v-5m0-10V2M2 4.5h5m-5 15h5M13 3l-1.734 4.509c-.282.733-.423 1.1-.643 1.408a3 3 0 0 1-.706.707c-.308.219-.675.36-1.408.642L4 12l4.509 1.734c.733.282 1.1.423 1.408.643.273.194.512.433.707.706.219.308.36.675.642 1.408L13 21l1.734-4.509c.282-.733.423-1.1.643-1.408.194-.273.433-.512.706-.707.308-.219.675-.36 1.408-.642L22 12l-4.509-1.734c-.733-.282-1.1-.423-1.408-.642a3 3 0 0 1-.706-.707c-.22-.308-.36-.675-.643-1.408L13 3Z"],"rules":["M11.302 21.615c.221.129.332.194.488.227.122.026.298.026.42 0 .156-.034.267-.098.488-.227C14.646 20.478 20 16.908 20 12V7.217c0-.799 0-1.199-.13-1.542a2 2 0 0 0-.548-.79c-.275-.243-.65-.383-1.398-.664l-5.362-2.01c-.208-.078-.312-.117-.419-.133a1 1 0 0 0-.286 0c-.107.016-.21.055-.419.133L6.076 4.22c-.748.28-1.122.421-1.398.664a2 2 0 0 0-.547.79C4 6.018 4 6.418 4 7.217V12c0 4.908 5.354 8.478 7.302 9.615Z"],"you":["M20 21c0-1.396 0-2.093-.172-2.661a4 4 0 0 0-2.667-2.667c-.568-.172-1.265-.172-2.661-.172h-5c-1.396 0-2.093 0-2.661.172a4 4 0 0 0-2.667 2.667C4 18.907 4 19.604 4 21M16.5 7.5a4.5 4.5 0 1 1-9 0 4.5 4.5 0 0 1 9 0Z"],"agent":["m21 21-4.35-4.35M19 11a8 8 0 1 1-16 0 8 8 0 0 1 16 0Z"],"filecheck":["M20 12.5V6.8c0-1.68 0-2.52-.327-3.162a3 3 0 0 0-1.311-1.311C17.72 2 16.88 2 15.2 2H8.8c-1.68 0-2.52 0-3.162.327a3 3 0 0 0-1.311 1.311C4 4.28 4 5.12 4 6.8v10.4c0 1.68 0 2.52.327 3.162a3 3 0 0 0 1.311 1.311C6.28 22 7.12 22 8.8 22H12m2-11H8m2 4H8m8-8H8m6.5 12 2 2 4.5-4.5"],"x":["M18 6 6 18M6 6l12 12"],"inbox":["M2.5 12h3.382c.685 0 1.312.387 1.618 1 .306.613.933 1 1.618 1h5.764c.685 0 1.312-.387 1.618-1 .306-.613.933-1 1.618-1H21.5M8.967 4h6.066c1.077 0 1.616 0 2.091.164a3 3 0 0 1 1.121.693c.36.352.6.833 1.082 1.796l2.166 4.333c.19.378.284.567.35.765.06.177.102.357.128.541.029.207.029.418.029.841V15.2c0 1.68 0 2.52-.327 3.162a3 3 0 0 1-1.311 1.311C19.72 20 18.88 20 17.2 20H6.8c-1.68 0-2.52 0-3.162-.327a3 3 0 0 1-1.311-1.311C2 17.72 2 16.88 2 15.2v-2.067c0-.422 0-.634.029-.84.026-.184.068-.365.128-.541.066-.199.16-.388.35-.766l2.166-4.333c.482-.963.723-1.444 1.082-1.796a3 3 0 0 1 1.12-.693C7.352 4 7.89 4 8.968 4Z"]};
  const ico = (n, cls = "") => `<svg class="ico-svg ${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${PATH[n].map((d) => `<path d="${d}"/>`).join("")}</svg>`;

  /* Raiffeisen's judging rubric (Understanding the Brief, 28 Oct 2026) */
  const RUBRIC = {
    orchestration: { label: "Agent design & orchestration", weight: 25 },
    testability: { label: "Functional completeness & testability", weight: 20 },
    originality: { label: "Originality & ingenuity", weight: 15 },
    domain: { label: "Problem research & domain understanding", weight: 15 },
    architecture: { label: "Architecture & reproducibility", weight: 15 },
    business: { label: "Business: users, value, adoption", weight: 10 },
  };

  /* UI-only facts the case record can't tell us (which buttons you used) */
  const ui = { timeoutUsed: false, verified: false, tamperCaught: false, packOpened: false };

  /* helpers over the case view (shape: backend/api.py view()) */
  const ev = (v, t) => v.events.some((e) => e.event_type === t);
  const codes = (f) => f.reason_codes || [];
  const executed = (v) => v.receipts.filter((r) => r.tool_call_status === "EXECUTED");
  const deniedWhere = (v, pred) => v.receipts.some((r) => r.tool_call_status === "DENIED" && pred(r));
  const hasPreflight = (v, p) => v.preflights.some((pf) => pf.plan_id === p.plan_id);
  const blockedPlans = (v) => v.plans.filter((p) => v.preflights.some((pf) => pf.plan_id === p.plan_id && pf.status === "BLOCKED"));
  const allStamped = (v) => v.claims.length > 0 && v.claims.every((c) => v.findings.some((f) => f.claim_id === c.claim_id));
  const closed = (v) => String(v.case.state).startsWith("CLOSED");
  const isS07 = (sid) => /^S07/.test(sid);

  /* Jobs to be done → objective → key results (each KR: done(view) + optional applies(view, scenario) + where to see it) */
  const JOBS = [
    {
      id: "J1", icon: "search", kid: "The bank's AI says something. We check if it is true.", short: "Verify the claims", nav: "Verify the claims", rubric: ["testability"],
      title: "Tell me what the agent got right, wrong, or can't prove",
      objective: "Every claim leaves with a verdict backed by a named source, never a guess.",
      scenarios: ["S01", "S05", "S04", "S03", "S08-OK"],
      krs: [
        { id: "J1.1", text: "The finding is split into claims, each with a check type and a time scope", how: "Done before anything runs.",
          done: (v) => v.claims.length > 0 && v.claims.every((c) => c.check_type) },
        { id: "J1.2", text: "Every claim carries a verdict stamp", how: "Approve a plan and start the checks.", done: allStamped },
        { id: "J1.3", text: "Every Confirmed or Contradicted stamp cites original evidence", how: "Shown under the stamps once the checks ran.",
          done: (v) => { const fs = v.findings.filter((f) => ["SUPPORTED", "CONTRADICTED"].includes(f.verdict)); return fs.length > 0 && fs.every((f) => f.supporting_evidence_ids.length + f.contradicting_evidence_ids.length > 0); } },
        { id: "J1.4", text: "A claim nobody can prove ends as Not enough evidence, never Confirmed", demo: "S03, S04 or a timed-out registry",
          applies: (v, sid) => ["S03", "S04", "S07"].includes(sid) || ui.timeoutUsed || v.findings.some((f) => f.verdict === "INSUFFICIENT_EVIDENCE"),
          done: (v) => v.findings.some((f) => f.verdict === "INSUFFICIENT_EVIDENCE") },
        { id: "J1.5", text: "A correct figure is Confirmed by arithmetic in code, not by the model", demo: "S05",
          applies: (v, sid) => sid === "S05", done: (v) => v.findings.some((f) => f.verdict === "SUPPORTED" && codes(f).includes("calculation_matches")) },
        { id: "J1.6", text: "The case is closed by your sign-off, not by the agent", how: "Sign off when the stamps are in.",
          applies: (v, sid) => !["S06", "S07-WD"].includes(sid), done: (v) => ev(v, "FINAL_SIGN_OFF") },
        { id: "J1.7", text: "Two documents that agree confirm the figure in code; a planted instruction changes nothing", demo: "S08-OK",
          applies: (v, sid) => sid === "S08-OK", done: (v) => allStamped(v) && v.findings.every((f) => f.verdict === "SUPPORTED") && ev(v, "INJECTION_FLAGGED") },
      ],
    },
    {
      id: "J2", icon: "clipboard", kid: "The AI must ask before it looks anything up. A person says yes or no.", short: "Approve the plan first", nav: "Approve the plan", rubric: ["orchestration"],
      title: "Let me approve exactly what the agent may do, before it does it",
      objective: "No lookup runs without a passed policy check and a human approval of the exact plan.",
      scenarios: ["S01", "S06", "S09"],
      krs: [
        { id: "J2.1", text: "A policy preflight ran on every plan version before you saw it", how: "Automatic, on every version.",
          done: (v) => v.plans.length > 0 && v.plans.every((p) => hasPreflight(v, p)) },
        { id: "J2.2", text: "A plan the policy check blocked could not be approved", demo: "S01, S03, S06 or S07",
          applies: (v, sid) => blockedPlans(v).length > 0,
          done: (v) => ev(v, "APPROVAL_REFUSED") || v.case.state === "CLOSED_BLOCKED" || blockedPlans(v).some((p) => ["SUPERSEDED", "REJECTED"].includes(p.status)) },
        { id: "J2.3", text: "Your restriction produced a new version with a fresh fingerprint and a fresh preflight", demo: "S01",
          applies: (v, sid) => !["S06", "S07-WD"].includes(sid) && (blockedPlans(v).length > 0 || v.plans.some((p) => p.version > 1)),
          done: (v) => v.approvals.some((a) => ["MODIFY", "REJECT"].includes(a.decision)) && v.plans.some((p) => p.version > 1 && p.supersedes && hasPreflight(v, p)) },
        { id: "J2.4", text: "You approved the exact plan fingerprint; nothing had run before that", how: "Approve the version the policy check passed.",
          applies: (v, sid) => !["S06", "S07-WD"].includes(sid),
          done: (v) => v.approvals.some((a) => a.decision === "APPROVE" && v.plans.some((p) => p.plan_id === a.plan_id && p.plan_hash === a.plan_hash)) },
        { id: "J2.5", text: "Every lookup that ran matched an approved step and went through the gate", how: "Start the approved checks.",
          applies: (v, sid) => !["S06", "S07-WD"].includes(sid),
          done: (v) => executed(v).length > 0 && executed(v).every((r) => r.authorization_decision === "ALLOW") },
        { id: "J2.6", text: "New scope made the agent ask again: new plan, new preflight, new approval", demo: "S01",
          applies: (v, sid) => ["S01", "S01-INJ"].includes(sid),
          done: (v) => v.plans.some((p) => p.supersedes && v.plans.some((q) => q.plan_id === p.supersedes && q.status === "APPROVED")) },
      ],
    },
    {
      id: "J3", icon: "lock", kid: "Some data may not be used. The rules stop the AI.", short: "Lawful sources only", nav: "Lawful sources", rubric: ["domain"],
      title: "Keep the agent inside the law on sources and personal data",
      objective: "The agent uses only sources the bank may lawfully use for this person, this purpose and this day.",
      scenarios: ["S07", "S07-OK", "S07-HOL", "S07-WD", "S08", "S09"],
      krs: [
        { id: "J3.1", text: "Consent validity is counted in Romanian working days, by code, with the rule id on the plan", demo: "S07 family",
          applies: (v, sid) => isS07(sid), done: (v) => v.preflights.some((pf) => pf.checks.some((ch) => /^SRC-/.test(ch.rule_id))) },
        { id: "J3.2", text: "A query the consent no longer covers is refused at run time: zero calls to ANAF", demo: "S07",
          applies: (v, sid) => sid === "S07", done: (v) => deniedWhere(v, (r) => r.tool_id === "anaf_income_query") },
        { id: "J3.3", text: "A refused source leaves the claim as Not enough evidence with the rule on record, never Confirmed", demo: "S07",
          applies: (v, sid) => sid === "S07", done: (v) => v.findings.some((f) => codes(f).includes("source_not_allowed")) },
        { id: "J3.4", text: "A consent still valid on day 5, or across public holidays, raises no false alarm", demo: "S07-OK, S07-HOL",
          applies: (v, sid) => ["S07-OK", "S07-HOL"].includes(sid), done: (v) => allStamped(v) && v.findings.every((f) => f.verdict === "SUPPORTED") },
        { id: "J3.5", text: "A withdrawn application, or a search for a person's private data, is blocked before any lookup", demo: "S07-WD, S06",
          applies: (v, sid) => ["S07-WD", "S06"].includes(sid), done: (v) => v.case.state === "CLOSED_BLOCKED" && v.case.tool_calls_used === 0 },
        { id: "J3.6", text: "An open web search about the subject blocks the plan; it is not just discouraged", demo: "S01, S03, S06",
          applies: (v, sid) => ["S01", "S01-INJ", "S03", "S06"].includes(sid) || v.plans.some((p) => p.steps.some((s) => s.tool_id === "unrestricted_web_search")),
          done: (v) => v.plans.some((p) => p.steps.some((s) => s.tool_id === "unrestricted_web_search") && v.preflights.some((pf) => pf.plan_id === p.plan_id && pf.status === "BLOCKED")) },
        { id: "J3.7", text: "Identifiers are masked (CNP, IBAN to the last 4) and GDPR Art. 9 rows are removed before anyone sees a result (POL-DATA-003)", demo: "S08",
          applies: (v, sid) => /^S08/.test(sid) || v.evidence.some((e) => e.fields && e.fields.masking),
          done: (v) => v.evidence.some((e) => e.fields && e.fields.masking && ((e.fields.masking.masked_fields || []).length > 0 || e.fields.masking.rows_removed_art9 > 0)) },
      ],
    },
    {
      id: "J4", icon: "shield", kid: "We try to trick the AI. It cannot leave the plan.", short: "Break-ins and failures", nav: "Break-ins", rubric: ["orchestration", "originality"],
      title: "Make sure nobody, not even the agent, can go off-plan",
      objective: "Every call outside the approved plan is denied before it reaches a tool, and a failure never becomes a confirmation.",
      scenarios: ["S01-INJ", "S08", "S02"],
      krs: [
        { id: "J4.1", text: "An open web search is denied at the gate; the tool is never called", how: "Test the safeguards: Agent tries an open web search.",
          done: (v) => deniedWhere(v, (r) => r.tool_id === "unrestricted_web_search") },
        { id: "J4.2", text: "A call caused by text inside a document, not by a plan step, is denied (provenance rule INJ-001)", how: "Test the safeguards: A document tells the agent to make a call. Happens by itself in S08 and S01-INJ.",
          done: (v) => deniedWhere(v, (r) => r.authorization_rule_ids.includes("INJ-001")) },
        { id: "J4.3", text: "A lookup about a different company than the approved step is denied (PLAN-001)", how: "Test the safeguards: Agent looks up a different company.",
          done: (v) => deniedWhere(v, (r) => r.tool_id === "company_registry_lookup" && r.authorization_rule_ids.includes("PLAN-001") && !r.authorization_rule_ids.includes("INJ-001")) },
        { id: "J4.4", text: "Instructions hidden in a source are flagged and treated as data: no call runs on a document's say-so", demo: "S01-INJ, S08",
          applies: (v, sid) => ["S01-INJ", "S08", "S08-OK"].includes(sid) || ev(v, "INJECTION_FLAGGED"), done: (v) => ev(v, "INJECTION_FLAGGED") },
        { id: "J4.5", text: "A source that times out leaves its claim as Not enough evidence, never Confirmed", how: "Test the safeguards: Make the court registry time out, then run the checks.",
          applies: (v, sid) => ui.timeoutUsed || ev(v, "TOOL_FAILED"), done: (v) => ev(v, "TOOL_FAILED") && v.findings.some((f) => f.verdict === "INSUFFICIENT_EVIDENCE") },
        { id: "J4.6", text: "A look-alike company (SRL vs GmbH) is caught by the identity check", demo: "S02",
          applies: (v, sid) => sid === "S02", done: (v) => v.findings.some((f) => f.verdict === "CONTRADICTED" && codes(f).includes("wrong_entity")) },
        { id: "J4.7", text: "Stop revokes every approval; anything further is blocked", how: "Optional: Stop this case, at the bottom of Test the safeguards.",
          done: (v) => v.case.stopped === true },
      ],
    },
    {
      id: "J5", icon: "archive", kid: "Everything is written down, so audit can check it later.", short: "Evidence pack for audit", nav: "Evidence pack", rubric: ["architecture", "originality"],
      title: "Give me an evidence pack I can hand to audit",
      objective: "Every decision is reconstructible from stored records, not from the AI's memory.",
      scenarios: ["S01", "S05"],
      krs: [
        { id: "J5.1", text: "Every plan version is kept with its fingerprint; old approvals stop working", how: "Automatic.",
          done: (v) => v.plans.length > 0 && v.plans.every((p) => p.plan_hash) },
        { id: "J5.2", text: "Every state change, decision and lookup is an event in a hash-chained log", how: "Automatic; open History to see the chain.",
          done: (v) => v.events.length > 0 && v.events.every((e) => e.event_hash) },
        { id: "J5.3", text: "Your sign-off is recorded as a review, separate from any banking decision", how: "Sign off the findings.",
          applies: (v, sid) => !["S06", "S07-WD"].includes(sid), done: (v) => ev(v, "FINAL_SIGN_OFF") },
        { id: "J5.4", text: "The evidence pack is built from the stored records and handed over", how: "Open the report or download the pack.",
          done: (v) => closed(v) && ui.packOpened },
        { id: "J5.5", text: "The log check passes on the stored log", how: "History → Tamper-evident log → Check the log.",
          done: () => ui.verified },
        { id: "J5.6", text: "A quietly edited entry is caught and named", how: "History → Simulate a tampered entry.",
          done: () => ui.tamperCaught },
      ],
    },
  ];
  const KR_TOTAL = JOBS.reduce((n, j) => n + j.krs.length, 0);
  const jobById = (id) => JOBS.find((j) => j.id === id);
  const jobsFor = (sid) => JOBS.filter((j) => j.scenarios.includes(sid));

  /* case status, from the backend state */
  const caseStatus = (c) => !c || !c.state ? "new" : c.stopped ? "blocked" : c.state === "CLOSED_VERIFIED" ? "verified" : c.state === "CLOSED_WITH_ISSUES" ? "issues"
    : c.state === "CLOSED_UNRESOLVED" ? "unresolved" : c.state === "CLOSED_BLOCKED" ? "blocked" : "open";
  const STATUS = { new: "Not started", open: "In progress", verified: "Closed, verified", issues: "Closed with issues", unresolved: "Closed, unresolved", blocked: "Closed, blocked" };

  /* what to do next, in one short sentence a first-time visitor can follow (the demo guide; E1) */
  const guide = (v) => {
    const c = v.case, last = v.plans[v.plans.length - 1];
    if (c.stopped) return "Stopped. Every approval is revoked. Pick another demo on the left.";
    switch (c.state) {
      case "RECEIVED": case "ASSESSED": return "Read what the bank's AI said. Its plan comes next.";
      case "PREFLIGHT_BLOCKED": return last && !last.steps.length ? "Nothing here can be checked lawfully. Click the yellow button to close the case as blocked."
        : "One step breaks a rule (marked red). Click the yellow button to remove it.";
      case "AWAITING_PLAN_APPROVAL": return "Every step is allowed. Click the yellow button to approve this exact plan.";
      case "LEGAL_REVIEW_REQUIRED": return "The rules can't decide this. Click “Ask compliance”.";
      case "APPROVED": return "Approved, nothing has run yet. Click the yellow button to let the agent check.";
      case "EXECUTING": return "The agent is checking. One moment.";
      case "FINDINGS_READY": case "REPLAN_REQUIRED": return "Look at the stamps on the right. The agent wants one more check.";
      case "AWAITING_FINAL_REVIEW": return "Look at the stamps on the right, then click the yellow button to sign off.";
      default: return closed(v) ? "Done. Click the yellow button to open the evidence pack." : "";
    }
  };

  /* ------------------------------------------------------------------ session scorecard */
  const KEY = "agent-assurance.okr.v1";
  let session = { done: {}, cases: {} }; // done: { krId: scenario it was first proven in }, cases: { scenarioId: { state, stopped } }
  try { const s = JSON.parse(sessionStorage.getItem(KEY) || "{}"); session = { done: s.done || {}, cases: s.cases || {} }; Object.assign(ui, s.ui || {}); } catch { /* storage unavailable: the scorecard just doesn't survive a reload */ }
  const save = () => { try { sessionStorage.setItem(KEY, JSON.stringify({ ...session, ui })); } catch { /* ignore */ } };

  let scenarios = [], cb = { open: () => {}, overview: () => {}, rerender: () => {}, teaches: {} };
  let view = { name: "overview", job: null, sid: null }, current = null, lastStatus = {}, tab = "progress";
  const scenario = (sid) => scenarios.find((s) => s.scenario_id === sid);
  const krStatus = (k, v, sid) => (k.applies && !k.applies(v, sid) ? "na" : k.done(v) ? "done" : "todo");
  const jobDone = (j) => j.krs.filter((k) => session.done[k.id]).length;
  const teaches = (sid) => (cb.teaches[sid] || {}).teaches || "";

  /* ------------------------------------------------------------------ routing: #/ · #/job/J1 · #/case/S01/J1 */
  const go = (hash) => { if (location.hash === hash) route(); else location.hash = hash; };
  function route() {
    const [, kind, a, b] = (location.hash.replace(/^#\/?/, "#/").match(/^#\/(job|case)?\/?([^/]*)\/?([^/]*)/) || []);
    document.body.classList.remove("nav-open");
    stopAuto();
    if (location.hash.startsWith("#/inbox")) return showInbox();
    if (kind === "job" && jobById(a)) { return startTour(jobById(a).scenarios.filter(scenario).map((x) => [x, a]), a); }
    if (kind === "case" && scenario(a)) {
      const job = jobById(b) ? b : (jobsFor(a)[0] || {}).id || null;
      const k = tour.queue.findIndex(([x, y]) => x === a && y === job);
      if (k >= 0) tour.i = k; else { tour = { queue: (jobById(job) ? jobById(job).scenarios : [a]).filter(scenario).map((x) => [x, job]), i: 0 }; tour.i = Math.max(0, tour.queue.findIndex(([x]) => x === a)); }
      if (!current || current.sid !== a) { view = { name: "case", job, sid: a }; lastStatus = {}; tab = "progress"; focusId = null; seen = {}; delete introSeen[a]; peek = null; show("case"); renderChrome(); cb.open(a, scenario(a).case_id); return; }
      view = { name: "case", job, sid: a }; lastStatus = {}; show("case"); return update(current.v);
    }
    showOverview();
  }
  function show(name) {
    $("overview").classList.toggle("hidden", name !== "overview");
    $("jobpage").classList.toggle("hidden", name !== "job");
    $("inbox").classList.toggle("hidden", name !== "inbox");
    $("workspace").classList.toggle("hidden", name !== "case");
    document.querySelector(".foot").classList.toggle("hidden", name !== "overview"); // the disclaimer lives on the overview; case pages stay on one screen
    window.scrollTo(0, 0);
  }

  /* ------------------------------------------------------------------ public */
  function boot(list, callbacks) {
    scenarios = list; cb = { ...cb, ...callbacks };
    $("menu").onclick = () => document.body.classList.toggle("nav-open");
    $("scrim").onclick = () => document.body.classList.remove("nav-open");
    document.querySelectorAll("[data-tab]").forEach((b) => b.onclick = () => setTab(b.dataset.tab));
    document.querySelectorAll("[data-mode]").forEach((b) => b.onclick = () => setMode(b.dataset.mode));
    setMode(mode, false);
    window.addEventListener("hashchange", route);
    route();
  }
  function showOverview() {
    view = { name: "overview", job: null, sid: null }; current = null;
    cb.overview(); show("overview"); renderChrome(); renderOverview(); setTitle("");
    const cta = $("overview").querySelector(".cta");
    cta.onclick = (e) => { e.preventDefault(); startTour(allDemos()); };
  }
  /* what a case waits for, from its state: the admin's to-do list */
  const WAITS = [
    ["LEGAL_REVIEW_REQUIRED", "compliance", "Compliance must decide", "rules"],
    ["PREFLIGHT_BLOCKED", "fix", "Remove a forbidden step", "rules"],
    ["AWAITING_PLAN_APPROVAL", "approve", "Approve the plan", "you"],
    ["APPROVED", "run", "Start the checks", "agent"],
    ["AWAITING_FINAL_REVIEW", "sign", "Sign the result", "you"],
  ];
  const waitOf = (v) => {
    const st = v.case.state;
    if (st === "LEGAL_REVIEW_REQUIRED" && v.events.some((e) => e.event_type === "COMPLIANCE_REQUESTED")) return ["compliance", "Compliance is deciding", "rules"];
    if (st === "PREFLIGHT_BLOCKED" && v.plans.length && !v.plans[v.plans.length - 1].steps.length) return ["fix", "Close a case nothing may check", "rules"];
    const w = WAITS.find(([s]) => s === st); return w ? w.slice(1) : null;
  };
  const waiting = () => Object.values(session.cases).filter((c) => c.waiting).length;
  async function showInbox() {
    view = { name: "inbox", job: null, sid: null }; current = null; stopAuto();
    cb.overview(); show("inbox"); renderChrome(); setTitle("Waiting for you");
    $("inbox").innerHTML = `<div class="inbox-head"><h1>Waiting for you</h1><p class="lead">Findings from the bank's AI agents that need a person.</p></div><div class="card inbox-list loading">${scenarios.map(() => `<div class="inbox-row skel"></div>`).join("")}</div>`;
    const who = ($("reviewer") && $("reviewer").value) || "demo-reviewer-01";
    // the inbox receives every finding: each one is loaded (or read back if it is already on the server)
    const views = await Promise.all(scenarios.map(async (sc) => {
      try { const r = await fetch(`/demo/scenarios/${sc.scenario_id}/load`, { method: "POST", headers: { "X-Reviewer-Id": who } }); return r.ok ? [sc, await r.json()] : [sc, null]; } catch { return [sc, null]; }
    }));
    if (view.name !== "inbox") return;
    const rows = [], done = [];
    for (const [sc, v] of views) {
      if (!v) continue;
      const w = waitOf(v);
      session.cases[sc.scenario_id] = { state: v.case.state, stopped: v.case.stopped, waiting: !!w };
      (w ? rows : done).push({ sc, v, w });
    }
    save(); renderChrome();
    const order = ["compliance", "fix", "approve", "run", "sign"];
    rows.sort((a, b) => order.indexOf(a.w[0]) - order.indexOf(b.w[0]));
    const job = (sid) => (jobsFor(sid)[0] || JOBS[0]).id;
    const row = ({ sc, v, w }, i) => `<a class="inbox-row" href="#/case/${sc.scenario_id}/${job(sc.scenario_id)}" title="${h(unId(v.case.raw_finding))}" style="animation-delay:${i * 0.04}s">
        <span class="actor-ico sm">${ico(w ? w[2] : "check")}</span>
        <span class="inbox-main"><span class="inbox-title">${h(sc.title)}</span><span class="inbox-sub">${h(unId(v.case.raw_finding))}</span></span>
        ${w ? `<span class="wait ${w[0]}">${h(w[1])}</span>` : `<span class="wait done">${ico("check")}Done</span>`}
        ${ico("right", "chev")}</a>`;
    $("inbox").innerHTML = `
      <div class="inbox-head"><h1>Waiting for you</h1><p class="lead">${rows.length ? `${rows.length} ${rows.length === 1 ? "finding needs" : "findings need"} a person. Most urgent first.` : "Nothing waits for you. Every case is closed."}</p></div>
      ${rows.length ? `<div class="card inbox-list">${rows.map(row).join("")}</div>` : ""}
      ${done.length ? `<details class="inbox-done"><summary>${done.length} closed</summary><div class="card inbox-list">${done.map(row).join("")}</div></details>` : ""}`;
  }
  function showJob(id) {
    view = { name: "job", job: id, sid: null }; current = null;
    cb.overview(); show("job"); renderChrome(); renderJob(id);
  }

  function update(v) {
    const sid = v.case.scenario_id || v.case.case_id;
    if (view.name !== "case" || view.sid !== sid) view = { name: "case", job: (jobsFor(sid)[0] || {}).id || null, sid };
    current = { v, sid };
    session.cases[sid] = { state: v.case.state, stopped: v.case.stopped, waiting: !!waitOf(v) && !closed(v) };
    for (const j of JOBS) for (const k of j.krs) if (krStatus(k, v, sid) === "done" && !session.done[k.id]) session.done[k.id] = sid;
    save();
    renderChrome(); renderCaseHead(v, sid); renderPanel(v, sid); focus(v);
  }

  function reset() {
    session = { done: {}, cases: {} }; lastStatus = {}; current = null;
    for (const k of Object.keys(ui)) ui[k] = false;
    save(); go("#/");
  }

  function setTab(name) {
    tab = name;
    document.querySelectorAll("[data-tab]").forEach((b) => { const on = b.dataset.tab === name; b.classList.toggle("on", on); b.setAttribute("aria-selected", on); });
    document.querySelectorAll("[data-pane]").forEach((p) => p.classList.toggle("hidden", p.dataset.pane !== name));
  }

  /* ------------------------------------------------------------------ chrome: sidebar + top bar */
  let lastCounts = {};
  function renderChrome() {
    const doneAll = Object.keys(session.done).length;
    const jobItem = (j) => {
      const d = jobDone(j), on = view.job === j.id && view.name !== "overview";
      const bump = lastCounts[j.id] !== undefined && lastCounts[j.id] !== d ? " bump" : ""; lastCounts[j.id] = d;
      return `<a class="nav-item${on ? " current" : ""}" href="#/job/${j.id}" aria-current="${on ? "page" : "false"}" title="${h(j.short)}">${ico(j.icon)}<span class="truncate">${h(j.nav || j.short)}</span>
        <span class="count${d === j.krs.length ? " full" : ""}${bump}">${d}/${j.krs.length}</span></a>`;
    };
    $("nav").innerHTML = `
      <a class="nav-item${view.name === "overview" ? " current" : ""}" href="#/">${ico("home")}<span class="truncate">Overview</span><span class="count">${doneAll}/${KR_TOTAL}</span></a>
      <a class="nav-item${view.name === "inbox" ? " current" : ""}" href="#/inbox">${ico("inbox")}<span class="truncate">Waiting for you</span>${waiting() ? `<span class="pending">${waiting()}</span>` : ""}</a>
      <p class="nav-label">Jobs to be done</p>
      ${JOBS.map(jobItem).join("")}`;
    const crumbs = [`<a href="#/">Overview</a>`];
    if (view.name === "inbox") crumbs.push(`<span aria-current="page">Waiting for you</span>`);
    const job = jobById(view.job);
    if (view.name !== "overview" && job) crumbs.push(view.name === "case" ? `<a href="#/job/${job.id}">${h(job.short)}</a>` : `<span aria-current="page">${h(job.short)}</span>`);
    if (view.name === "case") crumbs.push(`<span aria-current="page">${h(view.sid)}</span>`);
    $("crumbs").innerHTML = crumbs.join(`<span class="sep" aria-hidden="true">/</span>`);
  }

  /* ------------------------------------------------------------------ overview */
  function renderOverview() {
    const run = scenarios.filter((s) => session.cases[s.scenario_id]).length;
    const proven = Object.keys(session.done).length;
    const pct = Math.round((proven / KR_TOTAL) * 100);
    const rows = JOBS.map((j, i) => {
      const d = jobDone(j), p = Math.round((d / j.krs.length) * 100);
      return `<a class="job-row" href="#/job/${j.id}">
        <span class="job-icon">${ico(j.icon)}</span>
        <span class="job-main"><span class="job-name"><span class="job-n">Job ${i + 1}</span>${h(j.short)}</span><span class="job-obj diy-only">${h(j.objective)}</span><span class="job-obj watch-only">${h(j.kid)}</span>${(() => {
          const all = j.scenarios.filter(scenario), seenN = all.filter((x) => session.cases[x] && /^CLOSED/.test(session.cases[x].state)).length;
          return `<span class="seen ${seenN === all.length ? "all" : seenN ? "some" : ""}">${seenN === all.length ? `${ico("check")}All ${all.length} seen` : seenN ? `Seen ${seenN} of ${all.length}` : `${all.length} demos, not watched yet`}</span>`; })()}</span>
        <span class="job-weight">${j.rubric.map((r) => `${RUBRIC[r].weight}%`).join(" + ")}<small>${h(j.rubric.map((r) => RUBRIC[r].label.split(" ")[0]).join(", "))}</small></span>
        <span class="job-prog"><span class="bar${p === 100 ? " full" : ""}"><span style="width:${p}%"></span></span><span class="num">${d}/${j.krs.length}</span></span>
        ${ico("right", "chev")}</a>`;
    }).join("");
    $("overview").innerHTML = `
      <div class="hero">
        <div>
          <p class="eyebrow diy-only">Raiffeisen · AI for Operational Efficiency · NEXXT AI Hackathon 2026</p>
          <h1>Check what an AI agent claims, before anyone relies on it</h1>
          <p class="lead watch-only">Pick a job to see how it works.</p>
          <p class="lead diy-only">Five jobs a bank reviewer hires Agent Assurance for. Every demo ticks the key results it proves, straight from the case record.</p>
        </div>
        <div class="hero-cta">
          <a class="btn primary lg cta" href="#/case/S01/J1">${ico("play")}Play every demo</a>
          <span class="hint diy-only">or click any job: its demo starts by itself</span>
        </div>
      </div>
      <div class="score card diy-only">
        <div class="score-main"><span class="score-n">${proven}<small>/${KR_TOTAL}</small></span><span class="score-l">key results proven this session</span></div>
        <div class="score-bar"><span class="bar lg${pct === 100 ? " full" : ""}"><span style="width:${pct}%"></span></span><span class="score-meta">${run} of ${scenarios.length} demos run</span></div>
      </div>
      <div class="card list">${rows}</div>`;
  }

  /* ------------------------------------------------------------------ job page */
  function renderJob(id) {
    const j = jobById(id), n = JOBS.indexOf(j) + 1, d = jobDone(j), p = Math.round((d / j.krs.length) * 100);
    const demos = j.scenarios.map(scenario).filter(Boolean);
    const firstNew = demos.find((s) => !session.cases[s.scenario_id]);
    const demoCard = (s) => {
      const st = caseStatus(session.cases[s.scenario_id]);
      const primary = firstNew && firstNew.scenario_id === s.scenario_id;
      return `<a class="demo" href="#/case/${s.scenario_id}/${j.id}">
        <span class="demo-main"><span class="demo-title"><span class="demo-id">${h(s.scenario_id)}</span>${h(s.title)}</span>
        ${teaches(s.scenario_id) ? `<span class="demo-teaches">${h(teaches(s.scenario_id))}</span>` : ""}</span>
        <span class="badge ${st}">${STATUS[st]}</span>
        <span class="btn ${primary ? "primary" : "secondary"} sm">${ico("play")}${st === "new" ? "Run" : "Open"}</span></a>`;
    };
    const kr = (k) => {
      const by = session.done[k.id];
      return `<li class="kr ${by ? "done" : "todo"}"><span class="cb" aria-hidden="true">${by ? ico("check") : ""}</span>
        <span class="kr-text">${h(k.text)}${by ? `<em>Proven in ${h(by)}</em>` : ""}</span></li>`;
    };
    $("jobpage").innerHTML = `
      <div class="page-head">
        <span class="job-icon lg">${ico(j.icon)}</span>
        <div class="page-head-text">
          <p class="eyebrow">Job ${n} of ${JOBS.length} · ${j.rubric.map((r) => `${RUBRIC[r].weight}% ${h(RUBRIC[r].label)}`).join(" · ")}</p>
          <h1>${h(j.short)}</h1>
          <p class="lead">“${h(j.title)}”</p>
        </div>
      </div>
      <div class="objective card"><span class="label">Objective</span><p>${h(j.objective)}</p>
        <span class="obj-prog"><span class="bar${p === 100 ? " full" : ""}"><span style="width:${p}%"></span></span><span class="num">${d}/${j.krs.length} key results</span></span></div>
      <div class="split">
        <section><h2 class="section-title">Demos</h2><div class="demo-list card">${demos.map(demoCard).join("")}</div></section>
        <section><h2 class="section-title">Key results</h2><ul class="kr-list card pad">${j.krs.map(kr).join("")}</ul></section>
      </div>`;
  }

  /* ------------------------------------------------------------------ case: head + side panel */
  function renderCaseHead(v, sid) {
    const s = scenario(sid) || { title: sid };
    const st = caseStatus(session.cases[sid]);
    $("case-title").innerHTML = `
      <div class="head-row"><h1>${h(s.title)}</h1><span class="badge ${st}">${STATUS[st]}</span>
        <button class="btn secondary sm tools-toggle" id="tools-toggle">${document.body.classList.contains("show-tools") ? "Hide tools" : "Tools"}</button></div>`;
    $("tools-toggle").onclick = () => { document.body.classList.toggle("show-tools"); renderCaseHead(v, sid); };
  }

  function renderPanel(v, sid) {
    const job = jobById(view.job);
    const card = $("kr-card");
    if (!job) { card.innerHTML = ""; return; }
    const rows = job.krs.map((k) => ({ k, st: krStatus(k, v, sid) }));
    const applicable = rows.filter((r) => r.st !== "na");
    const done = applicable.filter((r) => r.st === "done").length;
    const pct = applicable.length ? Math.round((done / applicable.length) * 100) : 0;
    const others = jobsFor(sid).filter((j) => j.id !== job.id);
    const row = (r) => {
      const fresh = lastStatus[r.k.id] === "todo" && r.st === "done" ? " fresh" : "";
      const note = r.st === "na" ? `Not in this demo${r.k.demo ? `: see ${r.k.demo}` : ""}` : r.st === "todo" ? r.k.how || (r.k.demo ? `See ${r.k.demo}` : "")
        : session.done[r.k.id] && session.done[r.k.id] !== sid ? `Also proven in ${session.done[r.k.id]}` : "";
      return `<li class="kr ${r.st}${fresh}"><span class="cb" aria-hidden="true">${r.st === "done" ? ico("check") : ""}</span>
        <span class="kr-text">${h(r.k.text)}${note ? `<em>${h(note)}</em>` : ""}</span></li>`;
    };
    card.innerHTML = `
      <div class="kr-head"><div><p class="kr-eyebrow">Key results · ${h(job.short)}</p></div><span class="num">${done}/${applicable.length}</span></div>
      <span class="bar${pct === 100 ? " full" : ""}" role="progressbar" aria-label="Key results proven" aria-valuenow="${pct}" aria-valuemin="0" aria-valuemax="100"><span style="width:${pct}%"></span></span>
      <ul class="kr-list">${applicable.map(row).join("")}</ul>
      ${rows.some((r) => r.st === "na") ? `<details class="na"><summary>${rows.filter((r) => r.st === "na").length} more shown in other demos</summary><ul class="kr-list">${rows.filter((r) => r.st === "na").map(row).join("")}</ul></details>` : ""}
      ${others.length ? `<p class="kr-switch">Also covers ${others.map((j) => `<a href="#/case/${sid}/${j.id}">${h(j.short)}</a>`).join(" · ")}</p>` : ""}`;
    for (const r of rows) lastStatus[r.k.id] = r.st;
    setTab(tab);
  }

  /* ------------------------------------------------------------------ case: one step in focus, the rest one click away */
  const VERD = { SUPPORTED: "Confirmed", CONTRADICTED: "Contradicted", INSUFFICIENT_EVIDENCE: "Not enough evidence", NOT_CHECKED: "Not checked", PENDING: "Waiting" };
  const readable = (t) => (typeof plain === "function" ? plain(t) : t); // app.js turns source refs into words
  let focusId = null, seen = {};

  function focus(v) {
    const story = $("story");
    const steps = [...story.querySelectorAll(".step")].filter((s) => s.dataset.block !== "claims");
    const f = story.querySelector(".step.now") || steps[steps.length - 1];
    steps.forEach((s) => s.classList.toggle("off", s !== f));
    renderStage(v, f && f.querySelector("button.primary")); return;
    if (f) {
      f.querySelectorAll(".yourmove, .tap").forEach((x) => x.remove()); // idempotent: focus() may run twice on the same render
      f.classList.add("focus");
      if (f.classList.contains("past")) f.classList.add("open");
      const watch = mode === "watch", tip = watch ? narrate(v) : guide(v), end = closed(v) || v.case.stopped;
      const nxt = watch && end ? nextInTour() : null;
      const words = (t) => t.split(" ").map((w, i) => `<span class="w" style="animation-delay:${i * 40}ms">${h(w)} </span>`).join("");
      const endBar = !watch || !end ? "" : nxt
        ? `<span class="ym-next">Next: ${h(scenario(nxt[0]).title)}</span><span class="countdown" style="animation-duration:4500ms"></span>`
        : `<button class="btn secondary sm replay">${ico("reset")}Watch again</button>`;
      if (tip) f.querySelector("header").insertAdjacentHTML("afterend", `<div class="yourmove${watch ? " says" : ""}"><span class="ym-badge">${watch ? (tour.queue.length > 1 ? `${tour.i + 1}/${tour.queue.length}` : "Now") : "Your move"}</span><p>${watch ? words(tip) : h(tip)}</p>
        ${watch && !end ? `<span class="countdown" style="animation-duration:${waitFor(v) + 1130}ms"></span>` : ""}${endBar}</div>`);
      const rp = f.querySelector(".replay"); if (rp) rp.onclick = replay;
      if (nxt) { stopAuto(); timer = setTimeout(() => { if (mode === "watch") { tour.i++; go(`#/case/${nxt[0]}/${nxt[1]}`); } }, 4500); }
      const nx = f.querySelector(".body > .next");
      if (nx) {
        nx.classList.add("card-foot"); f.appendChild(nx);
        const cta = nx.querySelector("button.primary");
        if (cta) { cta.classList.add("cta"); cta.insertAdjacentHTML("afterend", `<span class="tap" aria-hidden="true">← click</span>`); }
        if (!nxt) autoplay(v, cta);
      } else if (!nxt) stopAuto();
      if (f.dataset.block !== focusId) { f.classList.add("enter"); if (focusId && end) confetti(); focusId = f.dataset.block; }
      // whatever the person must look at (a blocked step, a refused call) is scrolled into the card's view
      const body = f.querySelector(".body"), hot = body && body.querySelector(".check.blocked, .call.denied, .check.new, .verdict-banner.bad");
      if (hot) body.scrollTop = Math.max(0, hot.offsetTop - body.offsetTop - 12);
    }
    // the trail: every other step as a chip; click to read it in a slide-over
    const past = steps.filter((s) => s !== f);
    $("trail").innerHTML = past.length ? `<span class="trail-label">Done so far</span>${past.map((s, i) => `<button class="chip" data-past="${i}">${ico("check")}${h(s.querySelector("h3").textContent)}</button>`).join("")}` : "";
    $("trail").querySelectorAll("[data-past]").forEach((b) => b.onclick = () => {
      const s = past[+b.dataset.past], body = s.querySelector(".body").cloneNode(true);
      body.querySelectorAll(".next, .editor").forEach((x) => x.remove());
      slide(s.querySelector("h3").textContent, body.innerHTML);
    });
    renderClaims(v);
  }

  function renderClaims(v) {
    const fmap = Object.fromEntries(v.findings.map((x) => [x.claim_id, x]));
    const counts = {}; let k = 0;
    $("claims").innerHTML = v.claims.map((c, i) => {
      const f = fmap[c.claim_id], vd = f ? f.verdict : "PENDING";
      counts[vd] = (counts[vd] || 0) + 1;
      const fresh = f && seen[c.claim_id] !== vd ? " fresh" : "";
      const delay = fresh ? `style="animation-delay:${(k++) * 0.7}s"` : "";
      seen[c.claim_id] = vd;
      return `<button class="claim-mini${fresh ? " lit" : ""}" data-claim="${i}" ${delay}><span class="cm-text">${h(c.claim_text)}</span><span class="stamp ${vd}${fresh}" ${delay}>${VERD[vd]}</span>
        ${f ? `<span class="cm-reason">${h(readable(f.reason))}</span>` : `<span class="cm-reason">Not checked yet</span>`}</button>`;
    }).join("");
    $("claims-sum").textContent = `${v.findings.length} of ${v.claims.length} checked`;
    $("claims").querySelectorAll("[data-claim]").forEach((b) => b.onclick = () => {
      const full = $("story").querySelectorAll(".claim")[+b.dataset.claim];
      if (full) slide("Claim " + (v.claims[+b.dataset.claim].claim_id || ""), full.outerHTML);
    });
  }

  /* ------------------------------------------------------------------ watch mode: the demo plays itself */
  let mode = (() => { try { return sessionStorage.getItem(KEY + ".mode") || "diy"; } catch { return "diy"; } })();
  let timer = null;
  const ghost = () => $("ghost");
  function stopAuto() { clearTimeout(timer); timer = null; ghost().classList.remove("on", "tap"); }
  function setMode(m, refocus = true) {
    mode = m; try { sessionStorage.setItem(KEY + ".mode", m); } catch { /* ignore */ }
    if (m === "watch") { paused = false; peek = null; }
    document.body.classList.toggle("watch", m === "watch");
    $("modes").dataset.on = m;
    document.querySelectorAll("[data-mode]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.mode === m));
    stopAuto();
    if (!refocus) return;
    if (view.name === "case") cb.rerender(); else route(); // a clean re-render, never a second pass over the same DOM
  }
  /* one sentence per moment, like a subtitle */
  const narrate = (v) => {
    const c = v.case, last = v.plans[v.plans.length - 1];
    const stamps = () => v.claims.map((cl, i) => { const f = v.findings.find((x) => x.claim_id === cl.claim_id); return `Claim ${i + 1}: ${f ? VERD[f.verdict].toLowerCase() : "not checked"}.`; }).join(" ");
    if (c.stopped) return "Stopped. Every approval is revoked.";
    switch (c.state) {
      case "RECEIVED": case "ASSESSED": return "The bank's AI made a claim. We split it into small claims to check.";
      case "PREFLIGHT_BLOCKED": return last && !last.steps.length ? "Nothing here may be checked lawfully. The case closes as blocked."
        : "The plan wants a forbidden step. The rules block it, so it gets removed.";
      case "AWAITING_PLAN_APPROVAL": return v.plans.some((p) => p.status === "APPROVED") ? "The agent wants one more check. New scope needs a new approval."
        : "Every step is allowed now. A person approves this exact plan.";
      case "LEGAL_REVIEW_REQUIRED": return "The rules can't decide this one. Compliance has to look.";
      case "APPROVED": return "Approved. The agent may look things up now, only these things.";
      case "AWAITING_FINAL_REVIEW": return `Checked. ${stamps()} A person signs off.`;
      default: return closed(v) ? `Done. ${stamps()} Everything is in the evidence pack.` : "";
    }
  };
  const waitFor = (v) => (v.case.state === "AWAITING_FINAL_REVIEW" ? 4200 : 2600);
  /* the ghost cursor glides to a target and clicks it */
  function ghostClick(el, wait, then) {
    stopAuto();
    if (mode !== "watch" || !el) return;
    timer = setTimeout(() => {
      const r = el.getBoundingClientRect(), g = ghost();
      g.style.transform = `translate(${Math.round(r.left + Math.min(r.width * 0.6, 120))}px, ${Math.round(r.top + r.height * 0.55)}px)`;
      g.classList.add("on");
      el.classList.add("aimed");
      timer = setTimeout(() => {
        g.classList.add("tap");
        timer = setTimeout(() => { g.classList.remove("tap"); el.classList.remove("aimed"); if (document.body.contains(el) && mode === "watch") (then || (() => el.click()))(); }, 280);
      }, 850);
    }, wait);
  }
  function autoplay(v, cta) {
    if (mode !== "watch" || !cta || closed(v) || v.case.stopped) return stopAuto();
    ghostClick(cta, waitFor(v));
  }

  /* the tour: overview plays every demo, a job page plays that job's demos, one after another */
  let tour = { queue: [], i: 0 };
  const allDemos = () => { const done = new Set(), q = []; for (const j of JOBS) for (const sid of j.scenarios) if (scenario(sid) && !done.has(sid)) { done.add(sid); q.push([sid, j.id]); } return q; };
  function intro(jobId) {
    const j = jobById(jobId); if (!j) return Promise.resolve();
    const el = document.createElement("div"); el.className = "intro";
    el.innerHTML = `<div class="intro-card"><span class="job-icon xl">${ico(j.icon)}</span><p class="eyebrow">Job ${JOBS.indexOf(j) + 1} of ${JOBS.length}</p><h1>${h(j.short)}</h1><p class="intro-kid">${h(j.kid)}</p><span class="intro-skip">Click or press Space to skip</span><span class="countdown" style="animation-duration:3200ms"></span></div>`;
    document.body.appendChild(el);
    return new Promise((res) => {
      let done = false;
      const end = () => { if (done) return; done = true; el.classList.add("out"); setTimeout(() => { el.remove(); res(); }, 250); };
      el.onclick = end; setTimeout(end, 3200);
    });
  }
  async function startTour(queue, jobId) {
    stopAuto();
    tour = { queue, i: 0 }; paused = false; // a new tour always plays
    if (jobId) await intro(jobId);
    await fetch("/demo/reset", { method: "POST" });
    for (const [sid] of queue) delete session.cases[sid];
    save(); current = null;
    const [sid, job] = queue[0];
    location.replace(`#/case/${sid}/${job}`);
  }
  const nextInTour = () => tour.queue[tour.i + 1];

  function confetti() {
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const box = document.createElement("div"); box.className = "confetti"; box.setAttribute("aria-hidden", "true");
    const colors = ["#fee600", "#2b2d33", "#f1ede6", "#32ae88"];
    box.innerHTML = Array.from({ length: 36 }, (_, i) => `<i style="--x:${Math.round((Math.random() - .5) * 520)}px;--y:${Math.round(-160 - Math.random() * 260)}px;--r:${Math.round(Math.random() * 720 - 360)}deg;--d:${(Math.random() * .25).toFixed(2)}s;background:${colors[i % colors.length]}"></i>`).join("");
    document.body.appendChild(box);
    setTimeout(() => box.remove(), 2200);
  }

  function goDemo(step) {
    const t = tour.queue[tour.i + step]; if (!t) return;
    stopAuto(); tour.i += step; go(`#/case/${t[0]}/${t[1]}`);
  }
  const setTitle = (t) => { document.title = t ? `${t} · Agent Assurance` : "Agent Assurance"; };
  document.addEventListener("keydown", (e) => {
    const el = e.target instanceof Element ? e.target : null;
    if ((el && el.closest("input, textarea, select")) || e.metaKey || e.ctrlKey || e.altKey) return;
    const k = e.key;
    if (k === "Escape") { unslide(); return; }
    const intro = document.querySelector(".intro");
    if (intro && (k === " " || k === "Enter")) { e.preventDefault(); intro.click(); return; }
    if (view.name !== "case" || $("slide").classList.contains("open")) return;
    if (k === " " || k === "Enter") {
      if (el && el.closest("button, a") && k === "Enter") return; // a focused control handles its own Enter
      e.preventDefault();
      if (mode === "watch" && !peek) { const p = $("stage-pause"); if (p) p.click(); return; }
      const b = $("peek-back") || $("stage-btn") || $("stage-next"); if (b && !b.disabled) b.click();
    } else if (k === "ArrowRight") goDemo(1);
    else if (k === "ArrowLeft") goDemo(-1);
    else if (k === "r" || k === "R") replay();
    else if ((k === "p" || k === "P") && $("stage-pause")) $("stage-pause").click();
    else if (k === "t" || k === "T") openTools();
  });
  async function replay() {
    stopAuto();
    await fetch("/demo/reset", { method: "POST" });
    delete session.cases[view.sid]; save();
    const sid = view.sid; current = null; focusId = null; seen = {};
    cb.open(sid, scenario(sid).case_id);
  }

  /* ------------------------------------------------------------------ the stage: Watch mode, explained like to a child */
  const KID_SOURCE = {
    company_registry_lookup: "Company register", legal_case_status_lookup: "Court records", document_signature_check: "Signature check",
    document_metadata_lookup: "Document history", financial_report_lookup: "Financial reports", tax_status_lookup: "Tax register",
    consent_lookup: "Client's consent", application_status_lookup: "Loan application", anaf_income_query: "Income from ANAF",
    doc_read: "Client's documents", unrestricted_web_search: "Web search",
  };
  const KID_VERDICT = { SUPPORTED: ["True", "ok"], CONTRADICTED: ["False", "bad"], INSUFFICIENT_EVIDENCE: ["Can't tell", "warn"], NOT_CHECKED: ["Not checked", "warn"] };
  const ACTORS = [["ai", "Bank's AI"], ["rules", "Rules"], ["you", "You"], ["agent", "Our agent"]];
  const CHAPTERS = ["Claim", "Plan", "Approve", "Check", "Result"];
  const unId = (t) => String(t || "").replace(/\s*\([^)]*\d[^)]*\)/g, "").replace(/\s+([.,])/g, "$1").trim();
  const src = (t) => KID_SOURCE[t] || String(t).replace(/_/g, " ");
  // one pill per step: two steps on the same source differ by year or version ("Financial reports 2024", "Document history v2")
  const label = (s) => { const a = (s && s.arguments) || {}, v = /(v\d+)$/i.exec(a.document_id || ""); return src(s.tool_id) + (a.year ? ` ${a.year}` : v ? ` ${v[1]}` : ""); };
  const stepOf = (v, r) => { const p = v.plans.find((x) => x.plan_id === r.plan_id); return (p && p.steps.find((s) => s.step_id === r.step_id)) || { tool_id: r.tool_id }; };
  // why a stamp says what it says: the verifier's reason codes in plain words, and the dated source behind True/False
  const WHY = [["conflicting_versions", "The versions disagree and none is marked approved."], ["tool_error", "The source did not answer. Nothing was guessed."],
    ["source_not_allowed", "That source may not be used for this."], ["permission_unverifiable", "Permission could not be confirmed."],
    ["identity_unconfirmed", "We could not confirm it is the same company."], ["stale_source", "Only an old source mentions it."],
    ["no_current_record", "No current record was found."], ["field_not_found", "The filed reports do not have that figure."],
    ["no_source", "No source says this."], ["not_checked", "Not checked yet."], ["identity_not_checked", "Not checked yet."]];
  const day = (iso) => { const d = new Date(String(iso).slice(0, 10)); return isNaN(d) ? "" : d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }); };
  const because = (v, f) => {
    if (!f) return "";
    if (f.verdict === "SUPPORTED" || f.verdict === "CONTRADICTED") {
      const ids = f.verdict === "SUPPORTED" ? f.supporting_evidence_ids : f.contradicting_evidence_ids;
      const e = v.evidence.find((x) => x.evidence_id === ids[0]); // the verifier lists the deciding record first (signature/identity checks after it)
      if (!e) return "";
      const where = e.fields && e.fields.tool_id ? src(e.fields.tool_id) : "the attached document";
      return `Source: ${where}${e.published_at ? `, ${day(e.published_at)}` : ""}.`;
    }
    const hit = WHY.find(([code]) => (f.reason_codes || []).includes(code));
    return hit ? hit[1] : "";
  };
  const low = (t) => (/^(ANAF|Client)/.test(t) ? t : t.charAt(0).toLowerCase() + t.slice(1));
  let introSeen = {}, paused = false;

  /* what the stage shows for this moment of the case */
  function moment(v) {
    const c = v.case, last = v.plans[v.plans.length - 1];
    const pf = last && [...v.preflights].reverse().find((x) => x.plan_id === last.plan_id);
    const failed = (s) => pf && pf.checks.some((ch) => ch.step_id === s.step_id && ch.result === "FAIL");
    const prev = last && v.plans.find((p) => p.plan_id === last.supersedes);
    const removed = prev && prev.status !== "APPROVED" ? prev.steps.filter((s) => !last.steps.some((x) => x.tool_id === s.tool_id)) : [];
    const pills = (state) => [...(last ? last.steps : []).map((s) => ({ name: label(s), st: failed(s) ? "no" : state })), ...removed.map((s) => ({ name: label(s), st: "gone" }))];
    const laterRound = v.plans.filter((p) => p.status === "APPROVED").length > 1;
    const sid = c.scenario_id || c.case_id;
    if (c.stopped) return { actor: "you", ch: 4, say: "You stopped it. Nothing more can run.", scene: "result" };
    if (!introSeen[sid] && !closed(v)) return { actor: "ai", ch: 0, say: "The bank's AI said this. Is it true?", scene: "claim", auto: 3800 };
    switch (c.state) {
      case "PREFLIGHT_BLOCKED": {
        const bad = last ? last.steps.filter(failed).map((s) => src(s.tool_id)) : [];
        return last && !last.steps.length
          ? { actor: "rules", ch: 1, say: "Nothing here may be checked. The case stops.", scene: "plan", pills: pills("ok"), button: "Close the case" }
          : { actor: "rules", ch: 1, say: `The rules say no to the ${bad[0] ? low(bad[0]) : "forbidden step"}.`, scene: "plan", pills: pills("ok"), button: `Remove the ${bad[0] ? low(bad[0]) : "step"}` };
      }
      case "AWAITING_PLAN_APPROVAL": return v.plans.some((p) => p.status === "APPROVED")
        ? { actor: "you", ch: 2, say: "One more check, outside what you approved. You decide again.", scene: "plan", pills: pills("ok"), button: "Yes, approve" }
        : { actor: "you", ch: 2, say: "The plan is allowed now. You say yes.", scene: "plan", pills: pills("ok"), button: "Yes, approve" };
      case "LEGAL_REVIEW_REQUIRED": return v.events.some((e) => e.event_type === "COMPLIANCE_REQUESTED")
        ? { actor: "you", ch: 2, say: "Compliance has it. Nothing runs until they decide.", scene: "plan", pills: pills("wait"), button: "Close it as unresolved", use: "close-unresolved" }
        : { actor: "rules", ch: 1, say: "The rules can't decide this. Compliance must look.", scene: "plan", pills: pills("wait"), button: "Send it to compliance", use: "compliance" };
      case "APPROVED": return { actor: "agent", ch: 3, say: laterRound ? "You said yes again. Our agent checks only this new step." : "Our agent checks only these. Nothing else.", scene: "plan", pills: pills("wait"), button: "Start checking", checking: true };
      case "AWAITING_FINAL_REVIEW": return { actor: "you", ch: 4, say: "Here is what is true. You sign it.", scene: "result", button: "Sign it", wait: 4800 };
      default: return closed(v) ? { actor: "agent", ch: 4, say: "Done. Everything is saved for audit.", scene: "result", done: true } : { actor: "agent", ch: 3, say: "Working on it.", scene: "plan", pills: pills("wait") };
    }
  }

  let peek = null, running = null;
  function renderPeek(v, realCta) {
    const first = v.plans[0], pf0 = first && v.preflights.find((x) => x.plan_id === first.plan_id);
    const failed0 = (s) => pf0 && pf0.checks.some((ch) => ch.step_id === s.step_id && ch.result === "FAIL");
    const pill = (name, st, i) => `<div class="pill ${st}" style="animation-delay:${i * 0.1}s"><span class="pill-ico">${ico(st === "no" ? "x" : "check")}</span>${h(name)}${st === "no" ? "<em>not allowed</em>" : ""}</div>`;
    const DECIDE = { APPROVE: "You said yes to the plan", MODIFY: "You changed the plan", REJECT: "You said no to the plan" };
    let say = "", body = "";
    if (peek === "ai") {
      say = "This is what the bank's AI said.";
      body = `<div class="bubble">“${h(unId(v.case.raw_finding))}”</div>`;
    } else if (peek === "rules") {
      const bad = first ? first.steps.filter(failed0) : [];
      say = bad.length ? "The rules stopped what was not allowed." : "The rules let every step through.";
      body = `<div class="pills">${(first ? first.steps : []).map((s, i) => pill(label(s), failed0(s) ? "no" : "ok", i)).join("")}</div>`;
    } else if (peek === "you") {
      const acts = [...v.approvals.map((a) => DECIDE[a.decision] || a.decision), ...v.events.filter((e) => e.event_type === "FINAL_SIGN_OFF").map(() => "You signed the result")];
      say = acts.length ? "Every decision you made, in order." : "Nothing yet. Your turn comes soon.";
      body = acts.length ? `<ol class="decisions">${acts.map((t, i) => `<li style="animation-delay:${i * 0.12}s"><span class="n">${i + 1}</span>${h(t)}</li>`).join("")}</ol>` : "";
    } else {
      const looked = v.receipts.map((r) => ({ name: label(stepOf(v, r)), st: r.tool_call_status === "EXECUTED" ? "ok" : "no" }));
      say = looked.length ? "Where our agent looked. Red means it was stopped." : "Nothing yet. It waits for your yes.";
      body = looked.length ? `<div class="pills">${looked.map((x, i) => pill(x.name, x.st, i)).join("")}</div>` : "";
    }
    const at = ACTORS.findIndex(([k]) => k === peek);
    const actors = ACTORS.map(([k, label]) => `<button class="actor${k === peek ? " on" : ""}" data-actor="${k}" title="What did ${label} do?"><span class="actor-ico">${ico(k)}</span><span>${label}</span></button>`)
      .reduce((acc, a, i) => acc + (i ? `<span class="actor-line${i <= at ? " done" : ""}" aria-hidden="true"></span>` : "") + a, "");
    $("stage").innerHTML = `
      <div class="actors">${actors}</div>
      <div class="scene card enter peeking">
        <div class="say"><span class="say-who">${ico(peek)}</span><p>${say.split(" ").map((w, i) => `<span class="w" style="animation-delay:${i * 45}ms">${h(w)} </span>`).join("")}</p></div>
        <div class="scene-body">${body}</div>
        <button class="primary cta stage-btn" id="peek-back">Back to the demo</button>
      </div>
      <div class="stage-foot"><span class="stage-name">Looking back: ${h(ACTORS[at][1])}</span><button class="btn secondary sm" id="stage-tools">Tools</button></div>`;
    $("peek-back").onclick = () => { peek = null; if (mode === "watch") paused = false; focusId = null; renderStage(v, realCta); };
    $("stage-tools").onclick = openTools;
    wireActors(v, realCta);
  }
  function wireActors(v, realCta) {
    $("stage").querySelectorAll("[data-actor]").forEach((b) => b.onclick = () => {
      peek = b.dataset.actor; stopAuto(); if (mode === "watch") paused = true; renderPeek(v, realCta);
    });
  }
  function renderStage(v, realCta) {
    if (peek) return renderPeek(v, realCta);
    const m = moment(v), sid = v.case.scenario_id || v.case.case_id, sc = scenario(sid) || { title: sid }, diy = mode !== "watch";
    if (m.use) realCta = $("story").querySelector(`[data-act="${m.use}"]`) || realCta; // a step whose action is not the story's yellow button
    if (diy && m.auto) m.button = "Next";
    const fmap = Object.fromEntries(v.findings.map((x) => [x.claim_id, x]));
    const nxt = m.done ? nextInTour() : null;
    const at = ACTORS.findIndex(([k]) => k === m.actor);
    const actors = ACTORS.map(([k, label], i) => `<button class="actor${k === m.actor ? " on" : i < at ? " past" : ""}" data-actor="${k}" title="What did ${label} do?"><span class="actor-ico">${ico(k)}</span><span>${label}</span></button>`).reduce((acc, a, i) => acc + (i ? `<span class="actor-line${i < at ? " done" : i === at ? " flow" : ""}" aria-hidden="true"></span>` : "") + a, "");
    let scene = "";
    if (m.scene === "claim") {
      scene = `<div class="bubble">“${unId(v.case.raw_finding).split(" ").map((w, i) => `<span class="bw" style="animation-delay:${0.5 + i * 0.07}s">${h(w)} </span>`).join("")}”</div>
        <p class="scene-sub">We split it into ${v.claims.length} small ${v.claims.length === 1 ? "claim" : "claims"}:</p>
        <div class="claim-row">${v.claims.map((c, i) => `<div class="kid-claim" style="animation-delay:${0.6 + i * 0.35}s"><span class="n">${i + 1}</span>${h(unId(c.claim_text))}</div>`).join("")}</div>`;
    } else if (m.scene === "plan") {
      scene = `<p class="scene-sub">Where the agent wants to look:</p>
        <div class="pills">${(m.pills || []).map((p, i) => `<div class="pill ${p.st}" style="animation-delay:${i * 0.12}s"><span class="pill-ico">${p.st === "no" || p.st === "gone" ? ico("x") : p.st === "wait" ? ico("search") : ico("check")}</span>${h(p.name)}${p.st === "no" ? `<em>not allowed</em>` : ""}</div>`).join("")}</div>`;
    } else {
      scene = `<div class="verdicts">${v.claims.map((c, i) => { const f = fmap[c.claim_id]; const [word, cls] = f ? KID_VERDICT[f.verdict] : ["Not checked", "warn"];
          const fresh = f && seen[c.claim_id] !== f.verdict; seen[c.claim_id] = f ? f.verdict : undefined;
          const why = because(v, f);
          return `<div class="verdict ${cls}${fresh ? " fresh" : ""}" style="animation-delay:${i * 0.6}s"><p class="v-claim">${h(unId(c.claim_text))}</p><span class="v-word" style="animation-delay:${0.3 + i * 0.6}s">${word}</span>${why ? `<p class="v-why">${h(why)}</p>` : ""}</div>`; }).join("")}</div>
        ${m.done ? `<div class="saved"><svg class="draw-check" viewBox="0 0 52 52" aria-hidden="true"><circle cx="26" cy="26" r="24"/><path d="M15 27l7 7 15-16"/></svg>Saved for audit: every step, every decision.</div>` : ""}`;
    }
    const dots = CHAPTERS.map((t, i) => `<li class="${i < m.ch ? "done" : i === m.ch ? "now" : ""}">${t}</li>`).join("");
    const left = tour.queue.length > 1 ? `Demo ${tour.i + 1} of ${tour.queue.length}` : "Demo";
    setTitle(`${sid} · ${sc.title}`);
    $("stage").innerHTML = `
      <div class="actors">${actors}</div>
      <div class="scene card${focusId !== "stage:" + sid + ":" + m.scene + ":" + v.case.state ? " enter" : ""}">
        <div class="say"><span class="say-who">${ico(m.actor)}</span><p>${m.say.split(" ").map((w, i) => `<span class="w" style="animation-delay:${i * 45}ms">${h(w)} </span>`).join("")}</p></div>
        <div class="scene-body">${scene}</div>
        ${m.button ? `<button class="primary cta stage-btn" id="stage-btn">${m.button}</button>` : ""}
        ${m.done && nxt && diy ? `<button class="primary cta stage-btn" id="stage-next">Next demo ${ico("next")}</button>` : ""}
        ${m.done && !nxt ? `<button class="btn secondary stage-again" id="stage-again">${ico("reset")}${diy ? "Start again" : "Watch again"}</button>` : ""}
        <span class="countdown" id="stage-count"></span>
      </div>
      <div class="stage-foot">
        <ol class="chapters">${dots}</ol>
        <span class="stage-name">${left}: ${h(sc.title)}</span>
        ${nxt ? `<span class="stage-next">Next: ${h(scenario(nxt[0]).title)}</span>` : ""}
        <span class="nav-btns">
          <button class="btn secondary sm icon" id="stage-prev" title="Previous demo (←)" ${tour.i > 0 ? "" : "disabled"}>${ico("right", "flip")}</button>
          <button class="btn secondary sm icon" id="stage-restart" title="Restart this demo (R)">${ico("reset")}</button>
          <button class="btn secondary sm icon" id="stage-fwd" title="Next demo (→)" ${nextInTour() ? "" : "disabled"}>${ico("right")}</button>
        </span>
        ${diy ? "" : `<button class="btn secondary sm" id="stage-pause">${paused ? ico("play") + "Play" : ico("pause") + "Pause"}</button>`}
        <button class="btn secondary sm" id="stage-tools">Tools</button>
        <span class="keys" aria-hidden="true">Space ${diy ? "next step" : "pause"} · ← → demos</span>
      </div>`;
    focusId = "stage:" + sid + ":" + m.scene + ":" + v.case.state;
    if ($("stage-pause")) $("stage-pause").onclick = () => { paused = !paused; stopAuto(); renderStage(v, realCta); };
    $("stage-tools").onclick = openTools;
    $("stage-prev").onclick = () => goDemo(-1);
    $("stage-fwd").onclick = () => goDemo(1);
    $("stage-restart").onclick = replay;
    wireActors(v, realCta);
    const nb = $("stage-next"); if (nb) nb.onclick = () => { tour.i++; go(`#/case/${nxt[0]}/${nxt[1]}`); };
    const again = $("stage-again"); if (again) again.onclick = replay;
    const btn = $("stage-btn");
    const key = sid + ":" + v.case.state + ":" + v.plans.length + ":" + v.receipts.length + ":" + v.events.length;
    if (running && running !== key) running = null; // the case moved on: buttons work again
    const run = () => {
      if (m.auto) { introSeen[sid] = true; return renderStage(current.v, realCta); }
      if (running === key) return; // already pressed for this moment (by you or by the ghost)
      running = key;
      const b = $("stage-btn"); if (b) { b.disabled = true; b.classList.remove("cta"); }
      if (m.checking) {
        // the checking moment: each source lights up in turn, then the real call runs
        const pills = [...$("stage").querySelectorAll(".pill.wait")];
        pills.forEach((p, i) => setTimeout(() => { p.classList.add("checking"); setTimeout(() => { p.classList.replace("checking", "ok"); p.querySelector(".pill-ico").innerHTML = ico("check"); }, 450); }, i * 550));
        setTimeout(() => realCta && realCta.click(), pills.length * 550 + 500);
      } else if (realCta) realCta.click();
    };
    if (btn) { btn.onclick = run; if (running === key) { btn.disabled = true; btn.classList.remove("cta"); } }
    if (m.done && nxt) document.body.classList.add("confetti-once");
    if (focusId && m.done && !$("stage").dataset.cheered) { $("stage").dataset.cheered = sid; confetti(); }
    if (!m.done) delete $("stage").dataset.cheered;
    // timing: what happens next on its own
    stopAuto();
    if (paused || diy) return;
    const count = (ms) => { const el = $("stage-count"); el.style.animationDuration = ms + "ms"; el.classList.add("go"); };
    if (m.auto) { count(m.auto); timer = setTimeout(() => { introSeen[sid] = true; renderStage(current.v, realCta); }, m.auto); return; }
    if (m.done && nxt) { count(4200); timer = setTimeout(() => { tour.i++; go(`#/case/${nxt[0]}/${nxt[1]}`); }, 4200); return; }
    if (btn && running !== key) { const w = m.wait || 2800; count(w + 1100); ghostClick(btn, w, run); }
  }

  function openTools() {
    const tools = document.querySelector(".tools");
    $("slide-title").textContent = "Tools";
    $("slide-body").innerHTML = "";
    $("slide-body").appendChild(tools);
    tools.classList.add("in-slide");
    if (current) renderPanel(current.v, current.sid);
    $("slide").classList.add("open");
  }
  function slide(title, html) {
    const tools = $("slide-body").querySelector(".tools"); // put the tools back before reusing the slide-over
    if (tools) { tools.classList.remove("in-slide"); document.querySelector(".panel").appendChild(tools); }
    $("slide-title").textContent = title;
    $("slide-body").innerHTML = html;
    $("slide").classList.add("open");
    $("slide-close").focus();
  }
  const unslide = () => $("slide").classList.remove("open");
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") unslide(); });
  document.addEventListener("click", (e) => { if (e.target.closest("#slide-close, .slide-scrim")) unslide(); });

  return { boot, update, reset, ui, JOBS, RUBRIC };
})();
