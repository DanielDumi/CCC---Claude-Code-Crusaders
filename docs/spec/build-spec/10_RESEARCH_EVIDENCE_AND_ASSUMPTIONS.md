# 10 — Research Ledger, Verified Sources & Open Assumptions

**Cutoff:** 2026-10-28  
**Use:** Provenance and epistemic controls for Claude and the project team. Every pitch assertion about Raiffeisen, legal duties, competitors or ROI should be traceable to a fact tier.

## Evidence tags

- `[P]` **Primary public / verified:** Official public text reviewed for this package.
- `[T]` **Team-reported / direct conversation:** A contact or teammate said it, but not independently audited or published.
- `[I]` **Inference / testable hypothesis:** Plausible but not demonstrated for Raiffeisen.
- `[U]` **Unknown:** No reliable evidence available.
- `[D]` **Demo fiction:** Synthetic scenarios, data, and policies.

## 1. Project and challenge

| Claim | Tag | Evidence / caution |
|---|---|---|
| Hackathon is an open banking AI-agent challenge emphasizing originality, functioning prototype, architecture and feasibility | `[P]` for the uploaded official brief | `Brief Raiffeisen Bank.pdf`, provided in project workspace; document explicitly says open challenge, no predefined use cases |
| “Explore how AI agents can reduce repetitive work involving documents, data and verification” | `[T]` team's previously shared framing | Suitable problem framing; don't misstate as the *only* sentence from the official uploaded PDF |
| A small repeated verification subtask is better than a full banking pipeline for the MVP | `[I]` product decision | Focus constraints and demo feasibility |

## 2. Raiffeisen / RBI operating facts

| Claim | Tag | Source and limits |
|---|---|---|
| RBI has an AI Committee (AICO) and a database of **around 300 AI use-case entries** | `[P]` | [RBI Corporate Governance Report 2025](https://www.rbinternational.com/content/dam/rbi/ho/investors/corporate-governance/2026/RBI_CGB_2025_EN.pdf.coredownload.pdf). Entries are **not necessarily 300 live production agents** |
| AICO has responsibility for EU AI Act implementation and AI governance; monitored high-risk use cases involve Internal Audit coordination | `[P]` | Same official RBI report |
| RBI says it has **160+ live AI use cases** and centralized **AI Hub by Mobrix AI** for agentic pipelines | `[P]` | [RBI AI at RBI](https://www.rbinternational.com/en/raiffeisen/career/topics/ai-at-rbi.html), public group-wide page. Not a detailed audit of RBRO local platform |
| The AI Hub enables users to run/build/share agentic pipelines and onboarded tool connections | `[P]` | Same RBI AI at RBI page. **Do not propose replacing this platform** |
| RBI already describes audit trails for some AI use cases (e.g., ESG Criticality Checks) and model validation within its governance framework | `[P]` as self-description | Same RBI AI at RBI page. **Do not claim there is zero existing logging or independent verification group-wide** |
| Raiffeisen Bank Romania 2025 implemented AI+RPA for automated reading of SME onboarding documents | `[P]` | [Raiffeisen Bank Romania Annual Report 2025](https://www.raiffeisen.ro/content/dam/rbi/retail/eu/ro/documents/rapoarte/anuale/2025-Annual-Report-Raiffeisen-Bank.pdf.coredownload.inline.pdf) |
| Raiffeisen Romania has a large local AI platform with agents, documents, workflows and MCP tools | `[T]` | Direct team account of discussion; precise tool architecture is not publicly audited here |
| A specific discussed workflow currently lacks independent verification of tool data/agent conclusions | `[T]` | Team states this explicitly. **Scope is the discussed workflow**, not every Raiffeisen system |
| AI agent calls a web-scraping MCP to support customer-related research | `[T]` | Team's illustrative description; not proof this is a production-approved credit-scoring flow |
| Raiffeisen has **no** internal AI governance, MCP security or logs | `[U]` / contradicted as broad claim | Do **not** assert; public RBI evidence establishes group governance and some auditing |
| Average bank employee spends X minutes on this task | `[U]` | Must measure with bank reviewers; never invent a number |

## 3. EU AI Act and other official legal facts

| Fact | Tag | Official source |
|---|---|---|
| AI Act is Regulation (EU) 2024/1689 | `[P]` | https://eur-lex.europa.eu/eli/reg/2024/1689 |
| Amendment **Regulation (EU) 2026/1744** exists; published 24 July 2026, effective 27 July 2026 | `[P]` | https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32026R1744 |
| Annex III high-risk Chapter III sections 1–3 requirements apply **2 December 2027** under amended Art. 113 | `[P]` | Same amendment; https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-113 |
| Natural-person creditworthiness/credit scoring generally falls into Annex III 5(b), with explicit fraud-detection exception | `[P]` | https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-3 |
| Classification depends on intended use and Article 6; human intervention alone is not blanket exemption | `[P]` | https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-6 |
| Art. 12 requires log capabilities for high-risk systems | `[P]` | https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-12 |
| Art. 14 covers human oversight of high-risk systems | `[P]` | https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-14 |
| Art. 26 covers deployer obligations, including use, competent oversight, input-data relevance where controlled, monitoring and log retention conditions | `[P]` | https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-26 |
| Art. 27 FRIA applies to specific relevant deployers/use cases including Annex III 5(b)/(c) | `[P]` | https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-27 |
| GDPR independently requires lawful basis, purpose limitation, minimization and accuracy | `[P]` | https://eur-lex.europa.eu/eli/reg/2016/679/oj ; https://www.edpb.europa.eu/topics/key-gdpr-concepts/basic-principles_en |
| GDPR Article 22 regulates certain solely automated individual decisions | `[P]` | https://eur-lex.europa.eu/eli/reg/2016/679/oj |
| DORA exists and concerns ICT operational risk and third-party dependencies | `[P]` | https://eur-lex.europa.eu/eli/reg/2022/2554/oj |
| EBA 2025 mapping: no significant contradictions with surveyed financial rules; integration still may require work | `[P]` | https://eba.europa.eu/sites/default/files/2025-11/d8b999ce-a1d9-4964-9606-971bbc2aaf89/AI%20Act%20implications%20for%20the%20EU%20banking%20sector.pdf |

## 4. Important corrections to broad research statements

The user's provided Markdown `AI Act si Raiffeisen.md` (dated 2026-10-28) was used as **research input**, not treated as a legal ruling. Important qualifications:

| Overbroad version | Better implementation-safe version |
|---|---|
| “Human approval means our agent is not high-risk.” | High-risk classification depends on intended purpose and Article 6 criteria; assess the *assurance agent itself*, especially near natural-person lending. |
| “All AML/KYC and corporate processes are minimal risk.” | Not automatically Annex III 5(b), but specific systems/contexts and other legal obligations need assessment. |
| “EU AI Act obliges each bank to have an MCP verifier.” | It does not prescribe that product; it imposes relevant outcomes/obligations for scoped systems. |
| “The audit PDF proves we are AI Act compliant.” | A case-specific evidence pack can **support** controls; never replaces full legal/technical compliance. |
| “Public data can be scraped for credit decisions.” | Public availability alone does not supply GDPR lawful basis or bank permission. |
| “Raiffeisen does not monitor AI.” | RBI publicly describes committee governance and monitoring; team-reported missing check applies to a **specific** described workflow. |
| “300 use cases = 300 production agents requiring manual checks.” | RBI report refers to around 300 entries; a different official page says 160+ live use cases, group-wide. Neither proves manual hours. |
| “Banks all need every Annex IV and FRIA artifact.” | Duties differ by role, system classification, and intended use. |

## 5. What is still unknown / must be validated with mentors

| Question | Why it matters | Suggested interview language |
|---|---|---|
| Which local platform/framework accepts plugins/sidecars and tool events? | Integration feasibility | “Where can a verification hook receive an existing agent's output and MCP trace?” |
| How are MCP grants and data scopes enforced today? | Avoid duplicating controls | “Is the allowed source/tool scope centralized, case-specific or configured per agent?” |
| Which source-validation checks already exist? | True new value | “What part of evidence verification is still manual for the use case described?” |
| What original logs and source provenance are retained? | Evidence-pack completeness | “Can a reviewer retrieve the original tool request, response and timestamp?” |
| How many reviews happen and how much manual time do they require? | Economic rationale | “Could we shadow 3–5 representative cases and record investigator actions/time?” |
| What are relevant internal rules and owner-approved tool allowlists? | Legal/safety feasibility | “Could we use anonymized policy categories and synthetic tools for a demo?” |
| How does RBRO interface with RBI AICO? | Avoid parallel governance | “Would this pack map to an existing risk/control record?” |
| Is system intended purpose creditworthiness of natural persons? | AI Act classification | “What systems directly influence natural-person credit assessment versus corporate research?” |
| Who may approve plans and sign off findings? | Human oversight design | “Which user roles and segregation-of-duties rules apply?” |
| Are real personal-data queries permitted for pilot? | GDPR and security | Assume **no** without formal bank approval. |

## 6. Distinctive product hypothesis

**Not:** build an AI agent platform, repeat existing scoring, a generic AI Act checklist, or a one-pass LLM judge.

**Instead:** *Human-guided, dynamically replanned investigations with enforceable legal/policy preflight, scoped MCP execution, independent evidence citations and per-case governance records.*

This is **a product hypothesis to test**, not a claim no comparable vendor or internal tool exists. Potential overlaps: AI governance platforms, model-validation systems, exception-workflow tools, and RBI's own AI Hub. Competitive novelty must be demonstrated by **the particular integration and plan/approval/evidence workflow**, not by the presence of a dashboard or audit logs alone.

## 7. Demo material is fiction by design

All of these are `[D]`: `NOVA Logistics SRL`, `RO-DEMO-48219370`, `C-001`, 2024 historical dispute, 2026 closed status, synthetic document signatures, demo MCP endpoints, policy YAML, and ROI calculations before measurement. Always say “synthetic case.”

## 8. Primary source index (easy link checklist)

- **R01** RBI corporate governance 2025 — https://www.rbinternational.com/content/dam/rbi/ho/investors/corporate-governance/2026/RBI_CGB_2025_EN.pdf.coredownload.pdf
- **R02** RBI AI Hub + 160+ live use cases — https://www.rbinternational.com/en/raiffeisen/career/topics/ai-at-rbi.html
- **R03** Raiffeisen Romania annual report 2025 — https://www.raiffeisen.ro/content/dam/rbi/retail/eu/ro/documents/rapoarte/anuale/2025-Annual-Report-Raiffeisen-Bank.pdf.coredownload.inline.pdf
- **L01** AI Act original — https://eur-lex.europa.eu/eli/reg/2024/1689
- **L02** AI Act Digital Omnibus amendment — https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32026R1744
- **L03** Art. 6 classification — https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-6
- **L04** Annex III — https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-3
- **L05** Art. 12 logging — https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-12
- **L06** Art. 14 oversight — https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-14
- **L07** Art. 26 deployers — https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-26
- **L08** Art. 27 FRIA — https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-27
- **L09** Art. 113 dates — https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-113
- **L10** GDPR — https://eur-lex.europa.eu/eli/reg/2016/679/oj
- **L11** DORA — https://eur-lex.europa.eu/eli/reg/2022/2554/oj
- **L12** EBA mapping 2025 — https://eba.europa.eu/sites/default/files/2025-11/d8b999ce-a1d9-4964-9606-971bbc2aaf89/AI%20Act%20implications%20for%20the%20EU%20banking%20sector.pdf

## 9. Research hygiene rules for Claude

1. Prefer directly cited official EU law and bank reports; verify current legal amendments before use in production.
2. Mark each major external assertion `[P]`, `[T]`, `[I]`, `[U]`, or `[D]` in internal research.
3. Never assert a missing capability across an entire bank based on absence of a public source.
4. Do not infer measured time savings, risk reduction, or that a regulatory deadline is an automatic operational pain point.
5. Don't turn the team's hypothetical web-scraping credit use case into proof of deployed production scoring behavior.
6. Record both benefit evidence and disconfirming findings about existing RBI group platform/governance.
7. For every proposed MCP connection, identify its legitimate purpose, access policy, data categories, and provenance.
8. Whenever in doubt about legal applicability, output `LEGAL_REVIEW_REQUIRED`, not an invented legal conclusion.
9. Distinguish independent investigation from “another LLM agrees” throughout design and demos.
10. Do not promise “EU AI Act compliant” as a product outcome; say “supports applicable controls with reviewable evidence.”
