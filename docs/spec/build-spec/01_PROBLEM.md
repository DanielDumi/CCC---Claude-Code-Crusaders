# 01 — Problem Definition

**Project:** NEXXT AI / Agent Assurance  
**Date / evidence cutoff:** 2026-10-28  
**Document type:** Problem statement, workflow boundary, success hypothesis  
**Read with:** `02_FINAL_SOLUTION.md`, `10_RESEARCH_EVIDENCE_AND_ASSUMPTIONS.md`

## The problem in one sentence

A bank employee may have to repeatedly verify whether an AI agent's findings—or work already performed by another employee—are backed by current, authentic, authorized evidence, and whether further investigation is legally and operationally permitted.

## The precise repetitive task

**Target a small verification/investigation subtask, not the whole banking process.** A reviewer currently or potentially has to:

1. Read an agent's conclusion or a colleague's case notes.
2. Determine which factual assertions are material and which checks were omitted.
3. Reopen original documents, retrieved MCP responses, and internal records.
4. Cross-check entity identity, dates, document versions, and provenance.
5. Check which additional sources/tools may lawfully be consulted for this purpose.
6. Investigate contradictions and missing evidence, often through multiple steps.
7. Ask for a second opinion or approval where necessary.
8. Write down what was checked, by whom, with what result, and under what approval.

**Example:** An existing bank agent reports that an illustrative company has an *ongoing* dispute, citing a 2024 document. The existence of a historical dispute and the assertion that it is still ongoing are **different claims**. A human would otherwise need to investigate the current status using authorized sources and document the answer.

## Why ordinary extraction and database matching are insufficient

- Documents can be unstructured, contradictory, superseded, or incomplete.
- A case involves several claims with different evidence requirements.
- The next best check depends on what the previous check uncovered.
- The investigator must decide whether to request more evidence, try another **authorized** tool, or stop and escalate.
- Whether a fact is relevant is not the same question as whether its use is legally authorized.

**Agentic opportunity:** Let AI *plan and adapt the investigation* while deterministic systems control tool permissions, scope, and approvals.

## Two connected problems—not interchangeable

### A. Operational evidence gap

Existing AI output can be plausible yet unsupported, stale, attached to the wrong entity, or inconsistent with another record. Rechecking each item consumes employee effort. We have **not measured** actual Raiffeisen time loss.

### B. Governance and lawful-use gap

Before querying an external MCP or using personal data, the bank must determine that the action is authorized for the business purpose and consistent with applicable data protection, internal policy, and (where applicable) EU AI Act controls. A factual match does **not** prove lawful data collection or use. A legal permission check does **not** prove factual accuracy.

## Raiffeisen-specific context — evidence tiers

**Team-reported direct context (not a public audit):** Raiffeisen Romania uses a large existing AI agent platform with documents, pipelines, and MCP integrations. In the particular workflow discussed with the team, independent verification of retrieved data/agent conclusions is *not yet implemented*. The team has discussed an example involving an AI agent and a web-search MCP for a customer-related workflow.

**Public group-level context:** RBI's 2025 corporate governance report describes an AI Committee (AICO), an AI use-case database of around 300 entries, responsibility for AI Act implementation, and monitoring arrangements. **Do not claim** Raiffeisen has no governance, audit systems, or MCP security at bank-wide level. See `10_RESEARCH_EVIDENCE_AND_ASSUMPTIONS.md`.

**Not yet confirmed:** Frequency of manual reviews, minutes per investigation, number of affected cases, existing policy engine/telemetry architecture, production integration access, and internal security approval.

## Regulatory driver, carefully scoped

EU AI Act Regulation (EU) 2024/1689, amended by Regulation (EU) 2026/1744, sets requirements for **applicable** AI systems. AI used to assess the creditworthiness of *natural persons* is generally Annex III high-risk, subject to classification rules; not every banking agent is high-risk. Relevant features may support logging (Art. 12), human oversight (Art. 14), and deployer monitoring (Art. 26) **where applicable**. Main Annex III high-risk requirements apply from **2027-12-02**. GDPR and bank policy apply independently; the AI Act does not give permission to scrape people's data.

**Never pitch:** “The EU AI Act requires banks to install an MCP verification agent.” It does not.

## Problem boundaries and out-of-scope

**In:** verifying one received case, generating an approved investigation plan, executing read-only scoped checks, escalating uncertainty, and preserving reviewable evidence.

**Out:** building a credit-scoring model, automatically deciding a person's loan eligibility, an unrestricted people-search crawler, a bank-wide replacement of existing AI governance, or a legal-compliance certification product.

## Value hypothesis and how to prove it

| Hypothesis | Observable test | Must not assume |
|---|---|---|
| Human reviewers repeat evidence searches | Observe/document 3–5 representative verification cases | That a reviewer currently spends X minutes |
| Independent checks detect problematic output | Synthetic labeled scenarios; evaluate false positives and missed errors | That two LLMs independently imply truth |
| Adaptive planning reduces investigator actions | Compare manual workflow vs assisted workflow on matched cases | That more agent tool calls equal time saved |
| Human plan approval gives meaningful control | Reject/modify a plan, then inspect actual tool events | That a UI button is sufficient access control |
| Evidence pack helps review | Reviewer reconstructs evidence/approvals from pack | That a PDF alone equals AI Act compliance |

**MVP success:** Demonstrate at least one end-to-end investigation requiring a revised, human-approved plan; block unauthorized tool calls; produce claim-level findings linked to originals and a complete provenance/approval trace. Measure outcomes on synthetic data and label any time-saving estimates as unverified until benchmarked.

## End-user job to be done

> “I received an AI or colleague's finding. Tell me exactly which checks are missing, ask permission for a specific investigation plan, perform only the approved checks, show what the evidence proves or cannot prove, and give me a record I can defend.”

## References

- Actual hackathon participant brief supplied by team: an **open banking AI-agent challenge**, emphasizing useful original agent architecture, working demo, and feasibility; “AI for Operational Efficiency” is the team's positioning, not a restrictive use-case requirement in that PDF.
- Official RBI 2025 corporate governance report: https://www.rbinternational.com/content/dam/rbi/ho/investors/corporate-governance/2026/RBI_CGB_2025_EN.pdf.coredownload.pdf
- Consolidated AI Act / amendment: https://eur-lex.europa.eu/eli/reg/2024/1689 and https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32026R1744
