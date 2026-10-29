# Gate spec v1: why it is written the way it is

Companion to `Gate spec.md`, 28 Oct 2026, ~17:20. Written by claude (clow70's session). One section per design choice: the decision, the alternatives that were on the table today, why this one, the evidence, and what would change the decision. Evidence points to the team's research notes and to the primary sources those notes cite.

Labels: [public] dated public source · [draft] draft law · [vendor] a vendor's claim · [team-reported] mentor or insider, unverified · [design-to] a standard we build to, not a duty · [inference] our reasoning.

Research folders referred to below:
- `research_notes/Brainstorm idea refinement/` (five lenses: board, AI-agent governance, demo, architecture, red team)
- `research_notes/New EU rules for banks/` (AI Act, technical patterns, existing implementations)
- `research_notes/Loan origination GDPR focus/` (legal line on scoring, human-in-the-loop review, multi-reviewer precedents, state data sources)
- `research_notes/Onboarding KYC GDPR wedge/` (guardrails landscape, prompt injection)
- `reports/Team briefing.md`, `reports/Tech lead brief.md`, `reports/Refined concept and alignment.md`, and the vault proposals of 28 Oct

---

## 1. A gate at tool-call time, not only a plan approval

**Decision.** Every tool call is checked at the moment of execution, even when the plan was approved minutes earlier.

**Alternatives.** (a) Approve the plan and trust execution. (b) Rely on the MCP server's own authorisation. (c) Check after the fact from logs.

**Why.** State changes between approval and execution: a consent lapses at midnight, a client withdraws in the afternoon, a passport is superseded. The Raiffeisen fine of Nov 2024 was precisely access that was fine at one point in time and not later. MCP authorisation answers "may this client talk to this server", never "is there valid consent for this ANAF query for this purpose". A log-only sidecar detects and cannot block; Intesa needed blocking at query time, not a better report nineteen months later.

**Evidence.**
- MCP spec 2026-07-28: authorisation is optional and transport-level (OAuth 2.1 scopes); servers must not pass tokens upstream. Verified on modelcontextprotocol.io on 28 Oct (architecture lens) [public].
- ANSPDCP, 20 Nov 2024: an employee used a credit application after the client had withdrawn it, https://www.dataprotection.ro/?page=Comunicat_Presa_20_11_2024&lang=ro [public].
- Garante v Intesa Sanpaolo, 26 Mar 2026: about 6,600 queries on 3,573 clients; alerts counted queries; first detection about 19 months after the first access, https://www.thestar.com.my/tech/tech-news/2026/03/31/italy-data-protection-agency-fines-intesa-sanpaolo-36-million-over-data-breach [public].
- Architecture lens, candidate C "log sidecar": "detects and cannot block" [inference].

**What would change it.** Nothing short of a bank-wide gateway that already carries consent and case state per call; none was found.

## 2. Deterministic rules, no LLM inside the gate

**Decision.** The gate is plain code over YAML. An LLM may rephrase an explanation; a validator rejects any text whose rule IDs are not a subset of the rules that fired.

**Alternatives.** (a) An LLM "judge" that reads the envelope and decides. (b) LLM decides, rules only log.

**Why.** Where a rule has a right answer (a date, a status, a scope), an LLM adds variance and nothing else. It also opens the gate to injection: a deterministic validator cannot be talked out of a result. And the legal line is clear: anything that decides about a person with no real human discretion is an Art. 22 decision; keeping the decision logic in code with named rules is also what makes every denial explainable in the C-203/22 sense.

**Evidence.**
- Team decision "deterministic rules decide, LLM only classifies/explains", vault DECISIONS.md, 28 Oct [team].
- Guardrails note: classifiers are bypassable, up to 100% evasion against named products (Hackett et al., https://arxiv.org/abs/2504.11168) and 32%+ attack success even against purpose-trained defences (LLMail-Inject, https://arxiv.org/abs/2506.09956) [public]; "deterministic validators cannot be prompt-injected" [inference].
- CJEU SCHUFA C-634/21 as applied by OLG Nürnberg 3 U 247/25 (24 Jun 2025): a human "merely formally involved" is not enough, https://www.gesetze-bayern.de/Content/Pdf/Y-300-Z-GRURRS-B-2025-N-15991?all=True [public].
- Hamburg DPA, 30 Sep 2025, EUR 492,000 for automated rejections explained with boilerplate [public].

**What would change it.** Nothing for v1. An LLM may later propose *new* rules for a human to add to a pack; it still never decides a call.

## 3. Deny by default, with explicit permits, and forbid beats permit

**Decision.** A call is allowed only when a permit matches and no deny or hold fires. No matching rule is a deny.

**Alternatives.** (a) Allow unless a deny matches (blacklist). (b) Score-based risk thresholds.

**Why.** Blacklists are what Intesa had: thresholds on counts that stayed silent for years. Deny-by-default is what the French regulator asked for on agents ("granular user controls over which data agents may access"). It is also the semantics of Cedar, the engine AWS uses in AgentCore Policy, so the packs could later be exported into the gateway a bank already runs.

**Evidence.**
- CNIL and CIANum note, 20 Jul 2026, via Covington, https://www.insideprivacy.com/artificial-intelligence/french-cnil-publishes-note-on-agentic-ai-and-data-protection/ [public, secondary].
- AEPD, Feb 2026, "purpose drift" when one agent serves several purposes, via Covington [public, secondary].
- Cedar: default deny, forbid overrides permit, returns the deciding policy IDs, https://docs.cedarpolicy.com/auth/authorization.html [vendor docs]. AgentCore Policy GA 3 Mar 2026, https://aws.amazon.com/about-aws/whats-new/2026/03/policy-amazon-bedrock-agentcore-generally-available [vendor].
- Intesa, above.

**What would change it.** Nothing. This is the one principle a juror from the bank's risk function will test first.

## 4. Three outcomes, and `hold` is never `allow`

**Decision.** `allow`, `deny`, `hold`. A fact the gate cannot establish holds the call. A tool that fails after an allow is recorded as a failure. Neither becomes "Verified".

**Alternatives.** (a) Two outcomes, treat unknown as allow with a warning. (b) Treat unknown as deny.

**Why.** Silent passes are the failure mode regulators have already fined: the BNR fined Alpha Bank in 2023 for suspicious-transaction alerts closed automatically without analysis. Treating unknown as a hard deny is also wrong: a registry outage (e-Terra was down about a month in 2026) would then block every loan, which reads as cost. A hold keeps the claim open, shows it in "not checked", and lets a human release scope rules or wait for the source.

**Evidence.**
- BNR fines 2023, Alpha Bank reason "automatic suspicious-transaction alerts closed without analysis", https://www.profit.ro/povesti-cu-profit/financiar/banci/bnr-a-sanctionat-13-banci-cele-mai-multe-amenzi-au-fost-date-pentru-nerespectarea-legislatiei-pentru-combaterea-spalarii-banilor-inclusiv-faimoasa-actualizare-a-datelor-21462939 [public].
- e-Terra outage after the Jul-Aug 2026 cyberattack (departments report, SpotMedia) [public].
- Tech lead brief and vault GOTCHAS: "cannot_verify is never pass" [team].
- Human-in-the-loop note: the "not checked" list is "the main guard against false clears" [inference].

**What would change it.** Nothing. The demo's unexpected case depends on it.

## 5. Two authorisation layers: a standing passport and a per-case plan approval

**Decision.** An agent carries a passport (what the AI committee approved for that agent: tools, sources, actions, purposes, data categories, overseer, validity). A case carries an approved plan (what a human allowed for this file). A call must be inside both. `precheck` makes the plan approval informed, and a config switch decides whether a human sees every plan or only exceptions.

**Alternatives.** (a) Only the per-case approval from the schema's step 3. (b) Only an agent-level passport. (c) No approval, just the four checks.

**Why.** Step 3 alone makes every re-plan a human touch, and the red team's strongest attack was "a gate reads as cost, a desk saves time". The passport alone cannot express "not for this file". Together: routine plans inside the passport can proceed, and the human sees only what is outside the approved scope or predicted to fail. That is also the board-level story the research rated strongest: each agent arrives at the AI committee with its data controls already proven, so the bank gets more AI sooner. And the plan approval doubles as the forcing function against automation bias: the reviewer commits to *what should be checked* before being shown *what was found*.

**Evidence.**
- RBI's AI Committee (AICO) "must approve every use case" and RBI is hiring to "curate a catalog of AI use cases", https://www.rbinternational.com/en/raiffeisen/career/topics/ai-at-rbi.html [public]; "~300 use cases" is [team-reported], not sourced.
- Red team lens: weighted score about 3.4/5 as a gate; "reframe from a gate to a desk that finishes the work" [inference].
- Board lens: value proposition D, "each new agent arrives at the AI committee with its data controls already proven", chosen over the fines story [inference].
- Dutch DPA guidance on meaningful human intervention, 24 Jul 2025: time pressure and an unclear system make intervention not meaningful, https://www.autoriteitpersoonsgegevens.nl/documenten/handvatten-betekenisvolle-menselijke-tussenkomst [public]. Fewer, informed approvals beat many rubber stamps.
- Cognitive forcing reduces over-reliance (Buçinca et al., CHI 2021, https://arxiv.org/abs/2102.09692v1) [public, past trend]; AI Act Art. 14(4)(b) "remain aware of automation bias", https://artificialintelligenceact.eu/article/14/ [design-to].

**What would change it.** A mentor saying the bank's loan system already scopes agents per case, or that AICO approval is already machine-readable. Then the passport is an import, not a new record.

## 6. Some rules cannot be released; others can, once, with a reason

**Decision.** Legal-basis and status rules (CONS-*, STAT-001), passport validity, limits and STOP are not overridable. Scope and entitlement rules (PLAN-*, AGT-001..003, ENT-*, INJ-001) can be released by a compliance officer, once, bound to the exact envelope hash, with a reason code and text.

**Alternatives.** (a) Everything overridable by a sufficiently senior human. (b) Nothing overridable; re-plan instead.

**Why.** A missing consent is not a judgement call: querying ANAF without the client's consent is unlawful whoever signs off, and the only way through is to obtain the consent. A plan-scope deny is a judgement call: the officer may well want the agent to read a second payslip. Regulators expect overrides to exist *and* to be tracked with reasons; a ticket bound to one envelope is the narrowest override that still works.

**Evidence.**
- OPANAF 146/2022: consent required; the bank must archive consents and produce them on request, https://static.anaf.ro/static/IFN/OPANAF_146_2022.pdf [public].
- ANSPDCP, 25 May 2026: Court of Appeal upheld the fine on Vreau Credit for Credit Bureau queries without valid consent, https://www.dataprotection.ro/?page=Comunicat_Presa_25_05_2026&lang=ro [public].
- EBA GL/2020/06 para 54 (overrides and escalation inside the decision framework) and para 61 (tracking of "policy deviations, exceptions and overrides"), https://www.eba.europa.eu/sites/default/files/document_library/Publications/Guidelines/2020/Guidelines%20on%20loan%20origination%20and%20monitoring/884283/EBA%20GL%202020%2006%20Final%20Report%20on%20GL%20on%20loan%20origination%20and%20monitoring.pdf [public].
- AI Act Art. 14(4)(d): the overseer can "disregard, override or reverse the output" [design-to].

**What would change it.** Legal advice that the Credit Bureau query rests on legitimate interest at Raiffeisen (then CONS-BC-* changes shape, see 11).

## 7. One envelope for people and agents, and our own agent is gated

**Decision.** Subject is `human` or `ai_agent`. Our investigator has a passport and is checked like everyone else. An agent acting for a person inherits that person's entitlement.

**Alternatives.** (a) Separate products for staff access and agent access. (b) Trust our own agent.

**Why.** GDPR does not care who ran the query; the bank is the controller either way. Agents scale the human failure mode (OWASP "tool misuse within existing rights"). Gating our own investigator is the only way to show the loop's "autonomous investigation" stays inside an approved scope, and it is one line of code once the envelope exists.

**Evidence.**
- Demo lens: "GDPR doesn't care whether a person or a bot ran the query. The bank is the controller either way" [inference].
- OWASP Top 10 for Agentic Applications 2026 (9 Dec 2025): ASI02 Tool Misuse, ASI03 Identity and Privilege Abuse, via Giskard and Descope summaries [public, secondary].
- Architecture lens principle 4: "same gate for people and AI agents … that includes our own investigator" [team design].

**What would change it.** Nothing.

## 8. Per event, never per person; behaviour rules ship disabled

**Decision.** Rules fire per access event. There is no score, ranking or rolling count per employee in any output. ACC-004..007 (volume, after-hours, VIP, bulk) exist in the pack and are disabled by default.

**Alternatives.** (a) UEBA-style baselines per employee. (b) Drop the entitlement check entirely.

**Why.** AI that monitors or evaluates the behaviour of people in work relationships is Annex III point 4 of the AI Act, high-risk from 2 Dec 2027, and it also pulls in Romanian employee-monitoring law. "Unassigned to this file" and "file is closed" are facts about the case, not about the person; that is the line the research drew.

**Evidence.**
- AI Act Annex III point 4, https://eur-lex.europa.eu/eli/reg/2024/1689/oj; date shift to 2 Dec 2027 by Reg. 2026/1744 (K&L Gates, https://www.cyberlawwatch.com/2026/07/31/eu-digital-omnibus-on-ai-enters-into-force/) [public].
- Vault GOTCHAS "Check 4 can become AI Act high-risk" [team]; Law 190/2018 art. 5 conditions on employee monitoring [public, article text not yet verified].
- Refined concept, section 4: check 4 "rule-based and per access event only, no ML, no scores, no rankings" [team].

**What would change it.** A compliance mentor accepting per-employee baselines with staff informed in advance. Even then, keep them out of the demo.

## 9. Facts in code, rules in YAML, structured conditions, no DSL

**Decision.** Facts are small tested functions. Rules compare named facts with a fixed operator set and `all`/`any`/`not`. No `eval()`, no expression language.

**Alternatives.** (a) Rules as Python functions. (b) A policy engine now (Cedar via cedarpy, OPA). (c) A string DSL evaluated at runtime.

**Why.** YAML rules are reviewable by a compliance person and diffable by date, which is what the dated ANAF rule needs. A structured condition evaluator is an hour of work and has no injection surface. Cedar is attractive and is the engine inside AgentCore Policy, but the only Python binding has a single maintainer and is not AWS-supported, and Cedar has no holiday calendar; the facts library is where working days live anyway. "A new department is a new pack" is also the cheapest proof of modularity for the architecture criterion: drop in a second pack and show that only `packs/` changed.

**Evidence.**
- Tech lead brief section 4.5: "no policy engine has a holiday calendar"; cedarpy 4.12.2 single maintainer; fallback "~30 lines of Python" [team design].
- `holidays` package includes Romania and returns 30 Nov and 1 Dec 2026, https://github.com/vacanza/holidays; tested in the architecture lens [public].
- Architecture lens principle 6: "packs are data, not code … there is no eval()" [team design].
- Raiffeisen jury weight: architecture and reproducibility 15% [public, kickoff deck].

**What would change it.** A mentor confirming the bank runs AgentCore Gateway or another Cedar-based gateway; then export the packs as Cedar in v2 and keep the facts library as the attribute provider.

## 10. Working-day convention and the dated draft rule

**Decision.** Signing day excluded, valid through day 5 inclusive, Romanian public holidays skipped. The 5-day rule carries `effective_from: 2026-09-12` and the label `draft`, and can be switched off.

**Alternatives.** (a) Count the signing day. (b) Calendar days. (c) Hard-code the window without a date.

**Why.** No source states the counting convention, so the honest move is to pick one, write it into the rule, and test day 5 against day 6. The window itself is a draft order, so the rule must be dated and labelled; on stage we say "draft".

**Evidence.**
- Draft ANAF order reported 12 Sep 2026: consent in SPV, per purpose, valid 5 working days, https://economedia.ro/?p=371263 and https://financiarul.ro/economie/bancile-ar-putea-verifica-veniturile-prin-anaf-cu-acord-dat-in-spv/ [public, draft].
- Vault GOTCHAS: "the counting convention is not in our sources"; "across a Romanian holiday needs a holiday that exists" (Fri 27 Nov → Tue 8 Dec) [team].
- Team briefing section 7.3 [team].

**What would change it.** The adopted order's text. Change the rule, keep the date.

## 11. The Credit Bureau is modelled both ways

**Decision.** Config `bc_basis`: `legitimate_interest` (default) permits the bank's own query on an active application; a broker channel always needs consent. `consent` applies the ANAF-style tests without a window.

**Alternatives.** Pick one and hope.

**Why.** The sources conflict. BRD's and BT's privacy notices cite legitimate interest for the bank's own query, while BT also publishes a consent form, and the Vreau Credit ruling is about a broker's synthesis without consent. A gate that hard-codes the wrong basis would be wrong in a way a bank juror notices instantly.

**Evidence.**
- BRD notice, 24 Jul 2024, legitimate interest, https://www.brd.ro/sites/default/files/_files/newsletters/F305a%20Informare_prel_date_credite%2024072024.pdf [public, other bank, past trend].
- BT ACORD BC form, https://www.bancatransilvania.ro/uploads/ACORD%20BC.pdf, and BT credit-application notice citing legitimate interest (legal line note, section 4) [public, conflict].
- Vreau Credit ruling, above [public].

**What would change it.** One mentor answer; then delete the config and the losing branch.

## 12. Injection is a provenance rule, not a classifier

**Decision.** A call whose `caused_by` is a document span is denied by INJ-001 and flagged. The investigator receives typed fields from a quarantined extractor, never raw document text.

**Alternatives.** (a) Run a prompt-injection classifier on documents. (b) Trust the model's system prompt.

**Why.** Classifiers are bypassable and English-first; Romanian is "supported, not tuned" at best. The defensible design keeps untrusted text out of control flow, which is what CaMeL and spotlighting show and what OWASP recommends. Provenance is also something the gate can prove in the log: "this call was caused by line 14 of document 17".

**Evidence.**
- Guardrails note: AWS Bedrock Guardrails list Romanian as "Supported", not optimised, https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-supported-languages.html; Azure Prompt Shields "primarily trained and evaluated on English" [vendor docs]. Hackett et al. and LLMail-Inject, above [public].
- CaMeL, https://arxiv.org/abs/2503.18813; Spotlighting, https://arxiv.org/abs/2403.14720; CrackedPDFs (pipelines flatten the PDF before guardrails inspect it), https://arxiv.org/abs/2607.19396 [public].
- OWASP LLM01:2025, https://genai.owasp.org/llmrisk/llm01-prompt-injection/ [public].
- Note: no public, named bank incident of prompt injection was found in 2024-2026; the mentor claim about Raiffeisen's agent was later disputed. Do not say it on stage [team-reported, disputed].

**What would change it.** Nothing for the gate. A classifier (Prompt Guard 2) can be added as a cheap tripwire on free-text fields in v2.

## 13. Effectful actions are always held for a human

**Decision.** Request consent, schedule deletion, revoke access, send notice: the gate holds them until a DeskAction is approved by a named person. The plan approval does not count as approval of the effect.

**Alternatives.** Let an approved plan execute its actions.

**Why.** This is the team's one-line promise and the bank's own line: AI prepares, a human decides. It keeps every client-facing effect out of GDPR Art. 22 territory and gives the reviewer one screen with the follow-up work prepared, which is the "desk that finishes the work" framing the red team preferred to a gate.

**Evidence.**
- CEO Zdenek Romanek, 15 Aug 2026: AI can prepare a banking decision but should not have the last word, https://spotmedia.ro/stiri/economie/zdenek-romanek-ceo-raiffeisen-bank-ai-poate-pregati-o-decizie-bancara-dar-nu-ar-trebui-sa-aiba-ultimul-cuvant [public].
- 62.4% of Romanians reject AI decisions without human oversight, Agerpres 4 Jul 2025 [public].
- Interfaces-v2 proposal, DeskAction: "nothing executes before a human approves" [team].

**What would change it.** Nothing in this product.

## 14. Limits are rules

**Decision.** Rounds, calls per case, calls per source and wall-clock time are rules that deny with `next_step: escalate`.

**Alternatives.** Leave bounds to the agent runtime.

**Why.** The schema's loop "issues remain → new plan" has no visible limit. An unbounded loop is a cost risk, a data-minimisation risk (a second ANAF query is a second disclosure) and a demo risk. Putting the bound in the gate makes it enforceable regardless of which runtime calls the tools, and it gives the stop logic a place to live.

**Evidence.**
- Design proposal of 28 Oct, section 0: "max N evidence rounds per claim (e.g. 3), max tool calls per case; then INSUFFICIENT and escalate. Never a silent pass" [team].
- AI Act Art. 14(4)(e) stop control [design-to].
- GDPR Art. 5(1)(c) minimisation [public].

**What would change it.** Measured round counts from the eval; tune the numbers, keep the rules.

## 15. Hash-chained JSONL with IDs and hashes only

**Decision.** Append-only JSONL, each entry hashing the previous one, a `verify` command, the head hash printed periodically. No personal data values in the log. No QLDB. Object Lock is a slide line.

**Alternatives.** (a) A database table. (b) Amazon QLDB. (c) Full prompts and results in the log.

**Why.** The log is the evidence pack's spine and the jury can verify it from the repo in one command. Tamper evidence is a plus, not a legal requirement, so a cheap chain is enough. Full prompts would turn the log into a store of income figures and statement lines, which is the opposite of minimisation and could make the log itself an Art. 9 store. QLDB reached end of support in 2025; mentioning it costs credibility.

**Evidence.**
- AI Act Art. 12 (automatic logging) and Art. 26(6) (deployers keep logs at least six months), https://artificialintelligenceact.eu/article/26/ [design-to].
- EBA GL/2020/06 para 61 "effective audit trailing" [public].
- Law 190/2018 art. 4: processing the CNP needs minimisation and security measures [public].
- Tech lead brief: "Don't use or mention AWS QLDB (end of support 31 Jul 2025)"; "Art. 12 doesn't explicitly require tamper-proofing; ours is a plus" [team design].

**What would change it.** A bank requirement for a specific log platform; then the chain feeds it.

## 16. The MCP door is thin, second, and optional

**Decision.** The Python interface is the primary door. A FastMCP server with `on_call_tool` middleware is the second door, with tools that require `case_id`, `purpose`, `caused_by` and `consent_id`. Cut line Thu 01:00, replay fallback.

**Alternatives.** (a) Build the product as an MCP gateway. (b) Skip MCP entirely.

**Why.** Staff do not use MCP, and MCP gateways with tool-level policy are a crowded vendor category, so "first MCP gateway" is a losing claim. What the door proves is one thing the vendors do not: the same rule IDs fire for a person's screen action and an agent's tool call. FastMCP 4.1.4 is two days old, so it is pinned, and the server is plain, not a proxy, because middleware behaviour on proxies is undocumented.

**Evidence.**
- Architecture lens, verified on PyPI 28 Oct: `fastmcp` 4.1.4 (26 Oct), `mcp` 2.3.0; middleware since 2.9.0; proxy middleware undocumented [public].
- Permit.io, Cerbos, Gravitee and agentgateway sell MCP gateways with tool-level policy (architecture lens, 2026 vendor blogs) [vendor].
- Refined concept section 6: "Don't claim 'first MCP gateway'" [team].

**What would change it.** Nothing; the fallback keeps the claim.

## 17. Masking at the result stage, not in the decision

**Decision.** `filter_result` masks CNP and IBAN by role and removes special-category candidates from analyst views. The decision itself never reads document content.

**Alternatives.** (a) Decide on content. (b) No masking.

**Why.** Deciding on content would make the gate an LLM-shaped component and would need document text inside it. Masking after the call is data protection by default and the plain version of "who can't see the data can't leak it", which is the team's answer to the WhatsApp leak question. CNP detection itself is solved commercially and is not pitched as new.

**Evidence.**
- GDPR Art. 5(1)(c), 25(2), 32(4) [public]; ANSPDCP cases of staff access beyond need (Raiffeisen 2024, BT Jul 2026, ING Mar 2026) in the Team briefing section 3.2 [public].
- Microsoft Purview has a native Romanian CNP sensitive-information type, https://learn.microsoft.com/sv-SE/purview/sit-defn-romania-personal-numeric-code [vendor docs]; Presidio has no Romanian recogniser by default, https://microsoft.github.io/presidio/analyzer/languages [public].
- Team briefing section 3.8 "The WhatsApp question" [team].

**What would change it.** Time. Presidio custom recognisers and the LLM residue for free text are v2.

## 18. Explanations are templates, in English and Romanian

**Decision.** Each rule carries two templates filled from the facts it read. An LLM may rephrase for the case card; the validator rejects any rule ID that did not fire.

**Alternatives.** Free LLM prose.

**Why.** The explanation must match the decision exactly; a template cannot drift. Reviewers over-rely less on systems that state uncertainty in the first person and point to cheap-to-check evidence, so the template names the record and the date, not a generic warning. Romanian is for the officer and for the applicant letter later.

**Evidence.**
- Kim et al., FAccT 2024, N=404: first-person hedges reduced over-reliance, generic hedges did not, https://arxiv.org/abs/2405.00623 [public].
- CJEU C-203/22, 27 Feb 2025: explain which data were used and how, understandably; boilerplate is not enough [public].
- Tech lead brief: validator "cited rule IDs ⊆ rules that actually fired" [team design].

**What would change it.** Nothing.

## 19. What the gate deliberately is not

- Not a credit decision and not a score of a person: SCHUFA C-634/21 and its 2025-2026 applications (Austrian DSB KSV1870, VwGH 11 Jun 2026, OLG Nürnberg) and AI Act Annex III 5(b) from 2 Dec 2027 (legal line note) [public].
- Not a document-consistency checker: Raiffeisen announced its own on 14 Oct 2026, https://www.wall-street.ro/articol/banking/raiffeisen-bank-introduce-preaprobarea-financiara-digitala-pentru-ipotecare [public].
- Not employee monitoring and not personal-device monitoring: Annex III point 4; Law 190/2018 art. 5 [public, verify article text].
- Not an identity product: Entra Agent ID, Okta Cross App Access and AgentCore Policy exist (AI-agent governance lens) [vendor]. We add the business context they lack: consent, case status, committee purpose.

## 20. Honest weaknesses the spec does not fix

- **No measured volume anywhere.** Exceptions per month and minutes per case at Raiffeisen are unknown (Team briefing 3.13). Measure one case on camera; never put a bank number on a slide.
- **The loan system may already enforce part of this.** Public sources cannot tell. If it does, the gate is the investigation layer across systems, not the first lock.
- **The agent half is a forecast.** No public Raiffeisen agent that calls ANAF or the Credit Bureau was found; "ARIA with MCP" is unverified. Say "AI assistants that read documents and query systems".
- **"AI verifying AI" has competitors the research has not checked.** Governance platforms (Credo AI, watsonx.governance, OneTrust) are in the notes as [vendor]; evaluation and verification tooling from AWS and the observability vendors is not. Run the vendor check before any "nobody does this" line.
- **Two human touches per case can cost more than today** if `plan_approval_mode` stays `always` in production. The passport auto-approve path is the answer; the demo keeps the human step visible on purpose.

## 21. How the gate maps to the Raiffeisen criteria

- Agent design and orchestration, 25%: the plan is pre-checked, every call is a decision with tools, the loop is bounded, and `hold` is the handled unexpected case.
- Functional completeness and testability, 20%: one command runs the gate eval; false allows are reported first; `verify` is a thing the jury can run.
- Originality, 15%: per-call client consent for the bank's own outbound queries with a Romanian working-day calendar; access that follows the application's status; the same rule IDs for people and agents. Not: identity, not generic policy, not MCP gateways.
- Problem research and domain understanding, 15%: every rule cites its source and carries its label; the drafts are marked draft.
- Architecture and reproducibility, 15%: envelope, facts, packs, log; a second pack changes only `packs/`.
- Business mentoring, 10%: the open questions in the spec are the mentor questions.

## 22. Claims to make and not to make on stage (from the vault GOTCHAS and this spec)

Make: "consent checked at query time for the bank's own outbound queries, with the Romanian holiday calendar"; "access follows the application's status"; "same gate, same rule IDs, for a person and an AI agent"; "held, never allowed, when the source is down"; "every decision cites its rule and its source"; "we report misses first, on synthetic data, our measurement".

Do not make: "no layoffs"; "the bank lacks document AI"; "Raiffeisen's agent was prompt-injected"; "first MCP gateway"; "AI Act compliant"; any Raiffeisen volume or hours figure; "multi-agent system".
