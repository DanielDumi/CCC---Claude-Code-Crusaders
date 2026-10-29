"use strict";
/* Agent Assurance review screen.
   One case reads top to bottom as a story: the AI's finding, the claims (with verdict stamps), each plan the agent
   proposed with its automatic policy check and your decision, what the agent checked, and the sign-off + evidence pack.
   Only the current step is open and has one main action. All state lives in the backend; this file only renders it. */

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const app = { caseId: null, view: null, lastVerdicts: {}, open: new Set(), timeout: false, editing: false };

/* ------------------------------------------------------------------ plain-language vocabulary */
const TOOL = {
  company_registry_lookup: "Company registry",
  legal_case_status_lookup: "Licensed court-case registry",
  document_signature_check: "Document signature check",
  document_metadata_lookup: "Document version history",
  financial_report_lookup: "Filed financial reports",
  tax_status_lookup: "Tax registry",
  consent_lookup: "Consent register",
  application_status_lookup: "Loan application status",
  anaf_income_query: "ANAF income data (SPV)",
  doc_read: "Document reader (typed fields)",
  unrestricted_web_search: "Open web search",
};
const toolName = (t) => TOOL[t] || t;
const SOURCE = [
  [/demo:\/\/news-archive\/[^\s)]*/g, "the attached news article"],
  [/demo:\/\/licensed-legal-registry/g, "The licensed court-case registry"],
  [/demo:\/\/company-registry/g, "the company registry"],
  [/demo:\/\/financial-reports/g, "the filed financial reports"],
  [/demo:\/\/tax-registry/g, "the tax registry"],
  [/demo:\/\/documents/g, "the document store"],
  [/demo:\/\/consent-register/g, "the consent register"],
  [/demo:\/\/loan-applications/g, "the loan application system"],
  [/demo:\/\/anaf-income/g, "ANAF income data (SPV)"],
];
/* turn backend reasons (which cite source refs and tool ids) into readable sentences */
const plain = (t) => {
  let out = String(t || "");
  for (const [re, label] of SOURCE) out = out.replace(re, label);
  for (const [id, label] of Object.entries(TOOL)) out = out.replace(new RegExp(`^${id}: `), "").replace(new RegExp(id, "g"), label);
  return out.replace(/\bis (CLOSED|OPEN)\b/g, (m, w) => `is ${w.toLowerCase()}`).replace(/says (CLOSED|OPEN)/g, (m, w) => `says ${w.toLowerCase()}`);
};
const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
const VERDICT = {
  SUPPORTED: "Confirmed",
  CONTRADICTED: "Contradicted",
  INSUFFICIENT_EVIDENCE: "Not enough evidence",
  NOT_CHECKED: "Not checked yet",
  PENDING: "Waiting",
};
const VERDICT_HELP = {
  SUPPORTED: "An original, identifiable source backs this claim.",
  CONTRADICTED: "An authorised source says something different.",
  INSUFFICIENT_EVIDENCE: "The sources we were allowed to use can't settle it. Nothing was guessed.",
  NOT_CHECKED: "No permitted check has looked at this yet.",
};
const PREFLIGHT = {
  ALLOWED: { cls: "ok", head: "Policy check passed", text: "Every step uses an approved, read-only source." },
  ALLOWED_WITH_CONDITIONS: { cls: "ok", head: "Policy check passed, with conditions", text: "Approving accepts the conditions below." },
  BLOCKED: { cls: "bad", head: "Policy check blocked this plan", text: "A step breaks a rule, so this plan can't be approved. Remove that step or reject the plan." },
  LEGAL_REVIEW_REQUIRED: { cls: "warn", head: "Compliance has to decide", text: "The rules can't settle this. Nothing runs until compliance reviews it." },
};
const CLOSED = {
  CLOSED_VERIFIED: ["ok", "Closed: every claim is confirmed"],
  CLOSED_WITH_ISSUES: ["bad", "Closed with issues: at least one claim is contradicted"],
  CLOSED_UNRESOLVED: ["warn", "Closed unresolved: some claims could not be settled"],
  CLOSED_BLOCKED: ["bad", "Closed: no lawful way to investigate"],
};
const SCENARIOS = {
  "S01": { teaches: "Full walkthrough: a blocked plan, your restriction, a contradiction, a second approval round.", rec: true },
  "S01-INJ": { teaches: "A source tries to give the agent orders. It's ignored." },
  "S02": { teaches: "Bad news about a similarly named company abroad." },
  "S03": { teaches: "A claim with no source. The agent abstains instead of guessing." },
  "S04": { teaches: "Two versions of the same report disagree." },
  "S05": { teaches: "A correct claim, confirmed by arithmetic in code." },
  "S06": { teaches: "A search for a person's private data. Blocked outright." },
  "S07": { teaches: "Romanian consent rules: the ANAF income query is refused because the 5-working-day consent lapsed; the refusal is on the record." },
  "S07-OK": { teaches: "Same file on day 5: the consent is still valid, so no false alarm." },
  "S07-HOL": { teaches: "A consent signed before two public holidays (30 Nov, 1 Dec) is still valid on 8 Dec." },
  "S07-WD": { teaches: "The client withdrew the application. Nothing in the file may be touched, except for deletion." },
  "S08": { teaches: "Two income documents disagree (payslip vs bank statement). A planted instruction in the statement becomes a refused call; CNP and IBAN are masked and GDPR Art. 9 rows are removed before you see the data." },
  "S09": { teaches: "The case comes in for a purpose the bank never approved. The rules can't settle it, so it goes to compliance and nothing runs." },
  "S08-OK": { teaches: "The documents agree: no false alarm. The planted instruction is still refused." },
};

/* stages of a case, mapped from backend states */
const STAGES = [
  { key: "read", label: "Read the finding", states: ["RECEIVED", "ASSESSED"] },
  { key: "plan", label: "Approve a plan", states: ["PLAN_DRAFTED", "PREFLIGHT_BLOCKED", "LEGAL_REVIEW_REQUIRED", "AWAITING_PLAN_APPROVAL"] },
  { key: "run", label: "Agent investigates", states: ["APPROVED", "EXECUTING"] },
  { key: "find", label: "Findings", states: ["FINDINGS_READY", "REPLAN_REQUIRED"] },
  { key: "sign", label: "Your sign-off", states: ["AWAITING_FINAL_REVIEW"] },
  { key: "pack", label: "Evidence pack", states: ["CLOSED_VERIFIED", "CLOSED_WITH_ISSUES", "CLOSED_UNRESOLVED", "CLOSED_BLOCKED"] },
];
const stageIndex = (state) => STAGES.findIndex((s) => s.states.includes(state));

/* ------------------------------------------------------------------ api */
const reviewer = () => $("reviewer").value;
async function api(path, opts = {}) {
  const res = await fetch(path, { ...opts, headers: { "Content-Type": "application/json", "X-Reviewer-Id": reviewer(), ...(opts.headers || {}) } });
  const text = await res.text();
  let data; try { data = JSON.parse(text); } catch { data = text; }
  if (!res.ok) throw new Error(friendlyError(res.status, (data && data.detail) || text));
  return data;
}
function friendlyError(status, detail) {
  if (status === 403) return `You can't do that as ${reviewer()}: ${detail}. Switch "Acting as" to the case reviewer.`;
  if (/preflight BLOCKED/.test(detail)) return "This plan was blocked by the policy check, so it can't be approved. Remove the blocked step first.";
  if (/acknowledge/.test(detail)) return "Some claims are unresolved. Sign off with the acknowledgement button.";
  return detail;
}
function toast(msg, err = false) {
  const t = $("toast"); t.innerHTML = msg; t.className = "toast" + (err ? " err" : "");
  clearTimeout(toast.t); toast.t = setTimeout(() => t.classList.add("hidden"), 8000);
}
async function act(fn) {
  document.body.classList.add("busy"); // loading state: a bar on top, the current step's actions wait for the server
  try { await fn(); } catch (e) { toast(esc(e.message), true); }
  try { await refresh(); } finally { document.body.classList.remove("busy"); }
}

/* ------------------------------------------------------------------ boot */
async function init() {
  const info = await api("/demo/info");
  $("reviewer").innerHTML = info.users.map((u) => `<option value="${esc(u.reviewer_id)}">${esc(u.display_name)}</option>`).join("");
  const list = await api("/demo/scenarios");
  list.sort((a, b) => (a.scenario_id === "S01" ? -1 : b.scenario_id === "S01" ? 1 : a.scenario_id.localeCompare(b.scenario_id)));
  $("planner").textContent = info.llm === "mock" ? "Planner: scripted, no AI model" : `Planner: AI model (${info.llm.replace("bedrock:", "")})`;
  // the shell (sidebar, overview, job pages, side panel, routes) is okr.js; it calls back here to open a case
  OKR.boot(list, {
    open: (sid, caseId) => act(async () => {
      await api(`/demo/scenarios/${sid}/load`, { method: "POST" });
      app.caseId = caseId; app.sid = sid; app.lastVerdicts = {}; app.open.clear(); app.editing = false;
    }),
    overview: () => { app.caseId = null; app.view = null; },
    rerender: () => { if (app.view) render(app.view); },
    teaches: SCENARIOS,
  });
  $("switch-case").onclick = async () => {
    if (!confirm("Start over with a fresh demo? Every case in this session is cleared and the scorecard starts empty.")) return;
    await api("/demo/reset", { method: "POST" });
    app.caseId = null; app.view = null; app.timeout = false;
    OKR.reset();
  };
}

async function refresh() {
  if (!app.caseId) return;
  try { app.view = await api(`/cases/${app.caseId}`); } catch (e) {
    // the server lost this case (restart, or someone pressed Reset demo on a shared deploy): load it again once
    try { await api(`/demo/scenarios/${app.sid}/load`, { method: "POST" }); app.view = await api(`/cases/${app.caseId}`); } catch { toast(esc(e.message), true); return; }
  }
  render(app.view);
}

/* ------------------------------------------------------------------ render */
function render(v) {
  const c = v.case;
  const idx = stageIndex(c.state);
  const round = v.plans.filter((p) => p.status === "APPROVED").length + (["PLAN_DRAFTED", "PREFLIGHT_BLOCKED", "LEGAL_REVIEW_REQUIRED", "AWAITING_PLAN_APPROVAL"].includes(c.state) ? 1 : 0);
  $("rail").innerHTML = STAGES.map((s, i) => {
    const cls = c.stopped && i === idx ? "stopped" : i < idx ? "done" : i === idx ? "now" : "";
    const sub = i === idx && round > 1 && i <= 3 ? `<span class="sub">round ${round}</span>` : "";
    return `<li class="${cls}"><span>${s.label}${sub}</span></li>`;
  }).join("");
  $("rail-meta").textContent = `${c.subject.display_name}. ${c.tool_calls_used} of ${v.limits.max_total_tool_calls} lookups used. `
    + `Planner: ${v.llm === "mock" ? "scripted, no AI model" : v.llm.replace("bedrock:", "AI model ")}.`;

  const blocks = [findingBlock(v), claimsBlock(v)];
  const plans = v.plans;
  plans.forEach((p, i) => {
    blocks.push(planBlock(v, p, i === plans.length - 1));
    // calls from the "Try to break it" panel are shown there and in the activity feed, not here
    const calls = v.receipts.filter((r) => r.plan_id === p.plan_id && r.tool_call_status !== "DENIED");
    if (p.status === "APPROVED") blocks.push(runBlock(v, p, calls));
  });
  if (c.state === "AWAITING_FINAL_REVIEW") blocks.push(signBlock(v));
  if (c.state.startsWith("CLOSED")) blocks.push(packBlock(v));
  $("story").innerHTML = blocks.join("");
  wire(v);
  renderActivity(v);
  OKR.update(v); // sidebar, case head, next step, key results that this case has proven
  for (const f of v.findings) app.lastVerdicts[f.claim_id] = f.verdict;
}

function block({ id, title, when = "", now = false, past = false, summary = "", body = "" }) {
  const open = app.open.has(id);
  const cls = now ? "now" : past ? `past${open ? " open" : ""}` : "";
  return `<section class="step ${cls}" data-block="${esc(id)}">
    <header ${past ? `role="button" tabindex="0" aria-expanded="${open}"` : ""}><h3>${title}</h3><span class="when">${when}</span></header>
    ${past ? `<div class="summary">${summary}</div>` : ""}<div class="body">${body}</div></section>`;
}

function findingBlock(v) {
  const c = v.case;
  const now = ["RECEIVED", "ASSESSED"].includes(c.state);
  const gaps = v.gaps.filter((g) => !/^Original agent trace/.test(g));
  return block({
    id: "finding", title: "What the bank's AI agent said", now, past: !now,
    summary: `“${esc(c.raw_finding)}”`,
    body: `<blockquote class="quote">“${esc(c.raw_finding)}”<cite>${esc(c.origin_system.system_id)} about ${esc(c.subject.display_name)} (${esc(c.subject.reference_id)})</cite></blockquote>
      ${gaps.length ? `<p class="explain">Before looking anything up, the agent sees: ${gaps.map((g) => esc(g.replace(/^CL-\d+: /, ""))).join("; ")}.</p>` : ""}`,
  });
}

function claimsBlock(v) {
  const found = Object.fromEntries(v.findings.map((f) => [f.claim_id, f]));
  const evidence = Object.fromEntries(v.evidence.map((e) => [e.evidence_id, e]));
  const items = v.claims.map((cl) => {
    const f = found[cl.claim_id];
    const verdict = f ? f.verdict : "PENDING";
    const fresh = f && app.lastVerdicts[cl.claim_id] !== f.verdict ? " fresh" : "";
    const how = (id, dflt) => (evidence[id] && evidence[id].fields.tool_id === "document_signature_check" ? "checked the newer record's signature" : dflt);
    const evs = f ? [...f.supporting_evidence_ids.map((id) => [how(id, "backs it"), id]), ...f.contradicting_evidence_ids.map((id) => [how(id, "contradicts it"), id])] : [];
    return `<div class="claim">
      <div><div class="id">${esc(cl.claim_id)} · ${cl.temporal_scope === "CURRENT" ? "about now" : cl.temporal_scope === "HISTORICAL" ? "about the past" : "claim"}</div>
        <div class="text">${esc(cl.claim_text)}</div></div>
      <span class="stamp ${verdict}${fresh}" title="${esc(VERDICT_HELP[verdict] || "")}">${VERDICT[verdict]}</span>
      ${f ? `<div class="reason">${esc(plain(f.reason))}</div>` : ""}
      ${f && f.explanation ? `<div class="reason muted">${esc(f.explanation)}</div>` : ""}
      ${f && f.authenticity_limitations.length ? `<div class="limits">Limits: ${f.authenticity_limitations.map((x) => esc(plain(x))).join("; ")}</div>` : ""}
      ${evs.length ? `<div class="ev">${evs.map(([how, id]) => `${esc(sourceLabel(evidence[id]))} ${how}`).join(" · ")}</div>` : ""}
    </div>`;
  }).join("");
  return `<section class="step" data-block="claims"><header><h3>Claims</h3>
    <span class="when">${v.findings.length ? "updated as evidence arrives" : "not checked yet"}</span></header>
    <div class="body"><div class="claims">${items}</div></div></section>`;
}
function sourceLabel(e) {
  if (!e) return "a source";
  if (e.source_type === "ORIGINAL_CASE_ARTIFACT") return `Attached document (${(e.published_at || "").slice(0, 10) || "undated"})`;
  return `${toolName(e.fields.tool_id)} (${e.status === "AVAILABLE" ? "retrieved" : "unavailable"})`;
}

function planBlock(v, p, isCurrent) {
  const c = v.case;
  const pf = [...v.preflights].reverse().find((x) => x.plan_id === p.plan_id);
  const prev = v.plans.find((x) => x.plan_id === p.supersedes);
  const deciding = isCurrent && ["AWAITING_PLAN_APPROVAL", "PREFLIGHT_BLOCKED", "LEGAL_REVIEW_REQUIRED"].includes(c.state);
  const decision = [...v.approvals].reverse().find((a) => a.plan_id === p.plan_id);
  const P = pf ? PREFLIGHT[pf.status] : null;
  const stepChecks = (sid) => (pf ? pf.checks.filter((ch) => ch.step_id === sid) : []);
  const key = (s) => s.tool_id + JSON.stringify(s.arguments);
  const prevKeys = new Set(prev && prev.status !== "APPROVED" ? prev.steps.map(key) : []);
  const curKeys = new Set(p.steps.map(key));
  const removed = prev && prev.status !== "APPROVED" ? prev.steps.filter((s) => !curKeys.has(key(s))) : [];

  const steps = p.steps.map((s) => {
    const bad = stepChecks(s.step_id).find((ch) => ch.result === "FAIL");
    const isNew = prev && prev.status !== "APPROVED" && !prevKeys.has(key(s));
    return `<li class="check ${bad ? "blocked" : "ok"}${isNew ? " new" : ""}">
      <span class="ico" aria-hidden="true">${bad ? "✕" : "✓"}</span>
      <div><div class="what">${esc(toolName(s.tool_id))}</div>
        <div class="detail">${esc(s.objective)}${argText(s.arguments)}</div>
        ${bad ? `<div class="detail"><b>Why it's blocked:</b> ${esc(plain(bad.explanation))}</div>` : ""}</div>
      <span class="tag ${bad ? "bad" : "ok"}">${bad ? "blocked by policy" : "read-only, allowed"}</span></li>`;
  }).join("") + removed.map((s) => `<li class="check removed"><span class="ico" aria-hidden="true">−</span>
      <div><div class="what">${esc(toolName(s.tool_id))}</div><div class="detail">Removed after your change to version ${prev.version}</div></div><span></span></li>`).join("");

  const planChecks = pf ? pf.checks.filter((ch) => !ch.step_id && ch.result !== "PASS") : [];
  const conds = pf ? pf.conditions.filter((x) => !/^Excluded by reviewer/.test(x)) : [];
  const conditions = conds.length ? `<div><b>Conditions you accept by approving</b><ul>${conds.map((x) => `<li>${esc(plain(x))}</li>`).join("")}</ul></div>` : "";
  const decisionLine = decision ? `${{ APPROVE: "You approved", MODIFY: "You changed", REJECT: "You rejected" }[decision.decision]} version ${p.version}${decision.reason ? `: “${esc(decision.reason)}”` : ""}` : "";
  const blockedTools = p.steps.filter((s) => stepChecks(s.step_id).some((ch) => ch.result === "FAIL")).map((s) => s.tool_id);

  let actions = "";
  if (deciding) {
    const canApprove = pf && ["ALLOWED", "ALLOWED_WITH_CONDITIONS"].includes(pf.status) && p.steps.length;
    actions = `<div class="next">
      ${canApprove ? `<button class="primary" data-act="approve" data-plan="${esc(p.plan_id)}" data-hash="${esc(p.plan_hash)}">Approve version ${p.version}</button>` : ""}
      ${blockedTools.length ? `<button class="primary" data-act="fix" data-plan="${esc(p.plan_id)}" data-hash="${esc(p.plan_hash)}" data-tools="${esc(blockedTools.join(","))}">Remove ${esc(blockedTools.map(toolName).join(", "))} and re-check</button>` : ""}
      <button data-act="edit">Change the plan…</button>
      <button data-act="reject" data-plan="${esc(p.plan_id)}" data-hash="${esc(p.plan_hash)}">Reject</button>
      ${pf && pf.status === "LEGAL_REVIEW_REQUIRED" ? `<button data-act="compliance" data-plan="${esc(p.plan_id)}">Ask compliance</button>` : ""}
      ${c.state === "PREFLIGHT_BLOCKED" && !p.steps.length ? `<button class="primary" data-act="close-blocked">Close the case as blocked</button>` : ""}
      ${c.state === "LEGAL_REVIEW_REQUIRED" ? `<button data-act="close-unresolved">Close as unresolved</button>` : ""}
      <span class="why">${canApprove ? "Nothing has been looked up yet. Approving lets the agent run exactly these steps for 30 minutes." : "Approve isn't offered: the server refuses a blocked plan, even if someone forces the click."}</span>
    </div>
    ${app.editing ? editor(p) : ""}`;
  }

  const roundText = p.version === 1 ? "The agent's first plan" : prev && prev.status === "APPROVED" ? `The agent asks for more: version ${p.version}` : `Revised plan: version ${p.version}`;
  const intro = p.version > 1 && prev && prev.status === "APPROVED"
    ? `<div class="explain"><b>Why a new plan?</b> ${esc(p.rationale)}</div>`
    : `<p class="muted">${esc(p.rationale)}</p>`;
  const byModel = /\(bedrock:/.test(p.created_by);
  const proposer = `<p class="small muted">Proposed by ${byModel ? `the AI model (${esc(p.created_by.replace(/^.*\(bedrock:(.*)\)$/, "$1"))})` : "the scripted planner (no AI model)"}.</p>`;
  return block({
    id: p.plan_id, title: roundText, now: deciding, past: !deciding,
    when: p.status === "APPROVED" ? "approved" : p.status === "SUPERSEDED" ? "replaced" : p.status === "REJECTED" ? "rejected" : "waiting for you",
    summary: `${p.steps.map((s) => esc(toolName(s.tool_id))).join(", ") || "no permitted steps"} · ${P ? esc(P.head.toLowerCase()) : ""}${decisionLine ? ` · ${decisionLine}` : ""}`,
    body: `${intro}${proposer}
      <ul class="checks">${steps || `<li class="check blocked"><span class="ico">✕</span><div><div class="what">No permitted step can check these claims</div></div><span></span></li>`}</ul>
      ${P ? `<div class="verdict-banner ${P.cls}"><strong>${P.head}</strong><p>${P.text}</p>
        ${planChecks.map((ch) => `<p class="small">${esc(ch.explanation)}</p>`).join("")}</div>` : ""}
      ${conditions}
      <p class="fp">Fingerprint <code>${esc(p.plan_hash.slice(0, 12))}</code>. Any edit creates a new version; old approvals stop working.</p>
      ${decisionLine ? `<p><b>${decisionLine}</b></p>` : ""}
      ${actions}`,
  });
}
const argText = (a) => {
  const parts = Object.entries(a || {}).map(([k, val]) => `${k.replace(/_/g, " ")} ${val}`);
  return parts.length ? ` (${esc(parts.join(", "))})` : "";
};

function editor(p) {
  const tools = [...new Set(p.steps.map((s) => s.tool_id))];
  return `<div class="editor"><b>Change the plan</b>
    <p class="muted small">Your restrictions become part of the next version and stay for the rest of this case.</p>
    ${tools.map((t) => `<label><input type="checkbox" value="${esc(t)}" ${t === "unrestricted_web_search" ? "checked" : ""}> Don't use ${esc(toolName(t))}</label>`).join("")}
    <label for="edit-note" class="small">Note for the agent and the log</label>
    <textarea id="edit-note" rows="2">Only use the approved company registry and the licensed court registry. No open websites.</textarea>
    <div class="next"><button class="primary" data-act="send-edit" data-plan="${esc(p.plan_id)}" data-hash="${esc(p.plan_hash)}">Send changes and re-check</button>
      <button data-act="cancel-edit">Cancel</button></div></div>`;
}

function runBlock(v, p, calls) {
  const c = v.case;
  const isCurrent = v.case.current_plan_id === p.plan_id;
  const waiting = isCurrent && c.state === "APPROVED";
  const ev = Object.fromEntries(v.evidence.map((e) => [e.evidence_id, e]));
  const list = calls.map((r) => {
    if (r.tool_call_status === "DENIED") {
      return `<li class="call denied"><span class="ico" aria-hidden="true">✕</span><div><div class="what">Blocked by the gate: ${esc(toolName(r.tool_id))}</div>
        <div class="detail">${r.denial_reasons.map(esc).join("<br>")}</div><div class="detail">The tool was never called.</div></div></li>`;
    }
    const e = ev[r.response_evidence_ids[0]];
    if (r.tool_call_status === "FAILED") {
      return `<li class="call failed"><span class="ico" aria-hidden="true">!</span><div><div class="what">${esc(toolName(r.tool_id))} didn't answer</div>
        <div class="detail">${esc(r.error || "")}. The claim that needed it can't be confirmed.</div></div></li>`;
    }
    return `<li class="call run"><span class="ico" aria-hidden="true">✓</span><div><div class="what">Asked the ${esc(toolName(r.tool_id).toLowerCase())}${argText((p.steps.find((s) => s.step_id === r.step_id) || {}).arguments)}</div>
      ${e && e.original_excerpt ? `<blockquote>${esc(e.original_excerpt)}</blockquote>` : e ? `<div class="detail">${esc(summariseFields(e.fields))}</div>` : ""}
      ${e && e.untrusted_instruction_detected ? `<div class="detail" style="color:var(--bad)">This source contained instructions for the agent. They were treated as plain text and ignored.</div>` : ""}</div></li>`;
  }).join("");
  const skipped = v.events.filter((e) => e.event_type === "STEP_SKIPPED" && e.payload_refs.includes(p.plan_id));
  return block({
    id: `run-${p.plan_id}`, title: waiting ? "Ready to investigate" : `What the agent checked (version ${p.version})`, now: waiting, past: !waiting,
    summary: `${plural(calls.filter((r) => r.tool_call_status === "EXECUTED").length, "lookup", "lookups")}${calls.some((r) => r.tool_call_status === "FAILED") ? ", one source didn't answer" : ""}`,
    body: waiting
      ? `<p class="explain">The agent will run the approved steps in order. It may skip one it no longer needs; it can't add any.</p>
         <div class="next"><button class="primary" data-act="run">Start the approved checks</button></div>`
      : `<ul class="calls">${list || `<li class="muted">No lookups.</li>`}</ul>
         ${skipped.map((e) => `<p class="small muted">Skipped: ${esc(e.summary.replace(/^S\d+ /, ""))}</p>`).join("")}
`,
  });
}
const summariseFields = (f) => Object.entries(f).filter(([k]) => !["tool_id", "arguments"].includes(k)).map(([k, v]) => `${k.replace(/_/g, " ")}: ${v}`).join(", ");

function signBlock(v) {
  const unresolved = v.findings.some((f) => ["INSUFFICIENT_EVIDENCE", "NOT_CHECKED"].includes(f.verdict));
  const contradicted = v.findings.some((f) => f.verdict === "CONTRADICTED");
  const outcome = contradicted ? "closed with issues" : unresolved ? "closed as unresolved" : "closed as verified";
  return block({
    id: "sign", title: "Your sign-off", now: true,
    body: `<p class="explain">Check the stamps above. Signing off records your review, not a credit decision. The case will be ${outcome}.</p>
      <div class="next"><button class="primary" data-act="sign" data-ack="${unresolved}">${unresolved ? "Sign off, noting what's unresolved" : "Sign off the findings"}</button>
      <button data-act="more">Ask the agent to investigate more</button></div>`,
  });
}

function packBlock(v) {
  const c = v.case;
  const [cls, head] = CLOSED[c.state] || ["warn", c.state];
  const denied = v.receipts.filter((r) => r.tool_call_status === "DENIED").length;
  const run = v.receipts.filter((r) => r.tool_call_status === "EXECUTED").length;
  const decisions = v.approvals.length;
  return block({
    id: "pack", title: "Evidence pack", now: true,
    body: `<div class="verdict-banner ${cls}"><strong>${head}</strong><p>Built from the stored records and the log, not from the AI's memory.</p></div>
      <div class="pack-grid">
        <div class="fact"><div class="n">${v.plans.length}</div><div class="l">plan versions, all kept</div></div>
        <div class="fact"><div class="n">${decisions}</div><div class="l">human decisions on plans</div></div>
        <div class="fact"><div class="n">${run}</div><div class="l">lookups that ran</div></div>
        <div class="fact"><div class="n">${denied}</div><div class="l">calls the gate blocked</div></div>
      </div>
      <div class="next"><button class="primary" data-act="report">Open the report</button><button data-act="json">Download the pack (JSON)</button>
        <span class="why">Supporting evidence for AI Act and GDPR reviews, not a certificate.</span></div>`,
  });
}

/* ------------------------------------------------------------------ activity feed (plain language) */
const viaModel = (e) => (/bedrock:/.test(e.actor_id) ? " (AI model)" : /mock/.test(e.actor_id) ? " (scripted)" : "");
function renderActivity(v) {
  const rows = [];
  const say = (who, text) => rows.push(`<li><span class="who ${who}">${{ ai: "Agent", you: "You", gate: "Gate", sys: "System" }[who]}</span><span>${text}</span></li>`);
  for (const e of v.events) {
    const s = e.summary || "";
    switch (e.event_type) {
      case "CASE_RECEIVED": say("sys", "Case received from the bank's agent"); break;
      case "CLAIMS_ASSESSED": say("ai", `Split the finding into ${esc(s.split(" ")[0])} claims${viaModel(e)}`); break;
      case "PLAN_PROPOSED": say("ai", `Proposed plan version ${esc((s.match(/^v(\d+)/) || [])[1])}${viaModel(e)}`); break;
      case "PREFLIGHT_COMPLETED": { const st = s.split(" ")[0]; say(st === "BLOCKED" ? "gate" : "sys", esc((PREFLIGHT[st] || { head: st }).head)); break; }
      case "APPROVAL_REFUSED": say("gate", "Refused an approval for a blocked plan"); break;
      case "PLAN_MODIFY": say("you", "Changed the plan"); break;
      case "PLAN_REJECT": say("you", "Rejected the plan"); break;
      case "PLAN_APPROVED": say("you", `Approved ${esc(s.split(" ")[0].replace(/^PLAN-.*-v/, "version "))}`); break;
      case "TOOL_INVOKED": say("ai", `Looked up the ${esc(toolName(s.split("(")[0]).toLowerCase())}`); break;
      case "TOOL_FAILED": say("sys", `${esc(toolName(s.split("(")[0]))} didn't answer`); break;
      case "TOOL_DENIED": say("gate", `Blocked a call to ${esc(toolName(s.split(" ")[0]).toLowerCase())}`); break;
      case "INJECTION_FLAGGED": say("gate", "Ignored instructions hidden in a source"); break;
      case "STEP_SKIPPED": say("ai", "Skipped a step it no longer needed"); break;
      case "FINDING_UPDATED": { const [cid, verdict] = s.split(": "); say("ai", `${esc(cid)} stamped ${esc((VERDICT[(verdict || "").split(" ")[0]] || verdict || "").toLowerCase())}`); break; }
      case "EXPLANATIONS_WRITTEN": say("ai", "Wrote plain-language explanations"); break;
      case "COMPLIANCE_REQUESTED": say("you", "Asked compliance to review"); break;
      case "FINAL_SIGN_OFF": say("you", "Signed off"); break;
      case "FINAL_REQUEST_MORE_WORK": say("you", "Asked for more investigation"); break;
      case "STOP": say("you", "Stopped the case"); break;
      case "CLOSED_BLOCKED_BY_REVIEWER": say("you", "Closed the case as blocked"); break;
      default: break;
    }
  }
  $("activity").innerHTML = rows.reverse().join("") || `<li class="muted">Nothing yet.</li>`;
  $("events").innerHTML = v.events.slice().reverse().map((e) => `<li><b>${esc(e.event_type)}</b> <span class="muted">by ${esc(e.actor_type.toLowerCase())} ${esc(e.actor_id)}</span><br>${esc(e.summary)}<br><code>${esc(e.event_hash.slice(0, 12))} ← ${esc(e.previous_event_hash.slice(0, 12))}</code></li>`).join("");
}

/* ------------------------------------------------------------------ wiring */
function wire(v) {
  document.querySelectorAll(".step.past > header").forEach((h) => {
    const toggle = () => { const id = h.parentElement.dataset.block; app.open.has(id) ? app.open.delete(id) : app.open.add(id); render(app.view); };
    h.onclick = toggle; h.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); } };
  });
  document.querySelectorAll("[data-act]").forEach((b) => b.onclick = () => handle(b, v));
}

async function decide(planId, hash, decision, extra = {}) {
  return api(`/plans/${planId}/decisions`, { method: "POST", body: JSON.stringify({ decision, plan_hash: hash, ...extra }) });
}

function handle(b, v) {
  const d = b.dataset, cid = v.case.case_id;
  switch (d.act) {
    case "approve": return act(async () => { await decide(d.plan, d.hash, "APPROVE"); toast("Plan approved. Nothing has run yet; start the checks when you're ready."); });
    case "fix": return act(async () => {
      const tools = d.tools.split(",");
      const r = await decide(d.plan, d.hash, "MODIFY", { reason: `Remove ${tools.map(toolName).join(", ")}`, restrictions: { forbid_tools: tools, notes: [`Don't use ${tools.map(toolName).join(", ")}`] } });
      toast(`The agent made version ${r.plan.version}. Policy check: ${PREFLIGHT[r.preflight.status].head.toLowerCase()}.`);
    });
    case "edit": app.editing = true; return render(v);
    case "cancel-edit": app.editing = false; return render(v);
    case "send-edit": return act(async () => {
      const forbid = [...document.querySelectorAll(".editor input:checked")].map((i) => i.value);
      const note = ($("edit-note").value || "").trim();
      const r = await decide(d.plan, d.hash, "MODIFY", { reason: note || "Restricted by reviewer", restrictions: { forbid_tools: forbid, notes: note ? [note] : [] } });
      app.editing = false;
      toast(`The agent made version ${r.plan.version} with your changes. Policy check: ${PREFLIGHT[r.preflight.status].head.toLowerCase()}.`);
    });
    case "reject": return act(async () => {
      const reason = prompt("Why are you rejecting this plan? The agent will propose a new one.", "Scope too broad");
      if (reason === null) return;
      await decide(d.plan, d.hash, "REJECT", { reason });
    });
    case "compliance": return act(async () => { await api(`/plans/${d.plan}/compliance`, { method: "POST", body: JSON.stringify({ note: "Please confirm the legal basis" }) }); toast("Compliance asked. Nothing runs meanwhile."); });
    case "close-blocked": return act(() => api(`/cases/${cid}/close-blocked`, { method: "POST", body: JSON.stringify({ note: "No lawful investigation path" }) }));
    case "close-unresolved": return act(() => api(`/cases/${cid}/close-unresolved`, { method: "POST", body: JSON.stringify({ note: "Legal basis not established" }) }));
    case "run": return act(async () => {
      const r = await api(`/cases/${cid}/execute`, { method: "POST" });
      toast(r.replan ? "Checks done. The agent wants one more check, which is new scope: it needs a policy check and your approval." : "Checks done. Review the stamps, then sign off.");
    });
    case "sign": return act(async () => {
      await api(`/cases/${cid}/final-review`, { method: "POST", body: JSON.stringify({ decision: "SIGN_OFF", note: "Findings reviewed; any banking decision is separate.", acknowledge_unresolved: d.ack === "true" }) });
      toast("Signed off. The evidence pack is ready.");
    });
    case "more": return act(async () => {
      const note = prompt("What should the agent look into?", "Need more evidence for the open claims");
      if (note === null) return;
      await api(`/cases/${cid}/final-review`, { method: "POST", body: JSON.stringify({ decision: "REQUEST_MORE_WORK", note }) });
    });
    case "report": OKR.ui.packOpened = true; OKR.update(v); return window.open(`/cases/${cid}/pack.md?reviewer=${encodeURIComponent(reviewer())}`, "_blank");
    case "json": return act(async () => {
      OKR.ui.packOpened = true;
      const p = await api(`/cases/${cid}/pack`);
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([JSON.stringify(p, null, 2)], { type: "application/json" }));
      a.download = `${p.pack_id}.json`; a.click();
    });
  }
}

/* side panel: log + break-it */
$("verify").onclick = () => act(async () => {
  const text = await (await fetch(`/cases/${app.caseId}/ledger.jsonl?reviewer=${encodeURIComponent(reviewer())}`)).text();
  const r = await api("/ledger/verify", { method: "POST", body: text, headers: { "Content-Type": "text/plain" } });
  const o = $("verify-out"); o.className = "verify-out " + (r.ok ? "ok" : "bad");
  o.textContent = r.ok ? `The log is intact: all ${r.entries} entries chain correctly.` : `The log is broken at entry ${r.first_bad_index + 1}.`;
  if (r.ok) OKR.ui.verified = true;
});
$("tamper").onclick = () => act(async () => {
  const text = await (await fetch(`/cases/${app.caseId}/ledger.jsonl?reviewer=${encodeURIComponent(reviewer())}`)).text();
  const lines = text.trim().split("\n"); const i = Math.floor(lines.length / 2);
  const ev = JSON.parse(lines[i]); ev.summary += " (quietly edited)"; lines[i] = JSON.stringify(ev);
  const r = await api("/ledger/verify", { method: "POST", body: lines.join("\n"), headers: { "Content-Type": "text/plain" } });
  const o = $("verify-out"); o.className = "verify-out " + (r.ok ? "ok" : "bad");
  o.textContent = r.ok ? "Unexpected: the edit wasn't detected." : `We edited entry ${i + 1} in a copy of the log. The check catches it: broken at entry ${r.first_bad_index + 1}. The stored log is unchanged.`;
  if (!r.ok) OKR.ui.tamperCaught = true;
});
document.querySelectorAll("[data-break]").forEach((b) => b.onclick = () => act(async () => {
  if (!app.caseId) return;
  const kind = b.dataset.break;
  const out = $("break-out");
  if (kind === "timeout") {
    app.timeout = !app.timeout; OKR.ui.timeoutUsed = true;
    await api("/demo/fail-mode", { method: "POST", body: JSON.stringify({ tool_id: "legal_case_status_lookup", mode: app.timeout ? "timeout" : null }) });
    b.textContent = app.timeout ? "Bring the court registry back" : "Make the court registry time out";
    out.className = "break-out"; out.textContent = app.timeout ? "The court registry will now time out. Run checks to see the claim become “Not enough evidence”, never “Confirmed”." : "The court registry answers again.";
    return;
  }
  const body = {
    web: { tool_id: "unrestricted_web_search", arguments: { query: "NOVA director private finances" }, step_id: "S1" },
    inject: { tool_id: "company_registry_lookup", arguments: { company_id: "RO-DEMO-48219370" }, step_id: "S1", caused_by: "document_span" },
    offplan: { tool_id: "company_registry_lookup", arguments: { company_id: "RO-DEMO-11111111" }, step_id: "S1" },
  }[kind];
  const r = await api(`/cases/${app.caseId}/redteam/attempt-tool`, { method: "POST", body: JSON.stringify(body) });
  const ok = r.receipt.authorization_decision === "ALLOW";
  out.className = "break-out " + (ok ? "" : "ok");
  out.innerHTML = ok ? "This call matched an approved step, so it ran." :
    `<b>Blocked.</b> ${esc(plain(r.receipt.denial_reasons[0] || "").replace(/ \(hard deny[^)]*\)/, ""))}${r.receipt.denial_reasons.length > 1 ? ` (+${r.receipt.denial_reasons.length - 1} more reasons)` : ""}. The tool was never called.`;
}));
$("stop").onclick = () => act(async () => {
  if (!app.caseId || !confirm("Stop this case? Every approval is revoked and any further tool call is blocked.")) return;
  await api(`/cases/${app.caseId}/stop`, { method: "POST", body: JSON.stringify({ reason: "Stopped by reviewer" }) });
  toast("Case stopped. All approvals revoked.");
});

init().catch((e) => toast(esc(e.message), true));
