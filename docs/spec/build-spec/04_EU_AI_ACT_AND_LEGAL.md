# 04 — EU AI Act, GDPR, DORA & Bank Policy: Implementation Brief

**Law/evidence date:** 2026-10-28  
**Purpose:** Map applicable legal duties to **capabilities and evidence**, not generate a false compliance certificate.  
**Legal review required before production.** The legal knowledge base must be approved and versioned.

## 1. Official primary-law baseline

- **AI Act:** Regulation (EU) 2024/1689; modified by **Regulation (EU) 2026/1744** (Digital Omnibus on AI), published 2026-07-24 and effective 2026-07-27.
- **Application timing:** Main Annex III high-risk obligations in Chapter III Sections 1–3 apply **2027-12-02**; Annex I product-linked high-risk **2028-08-02**. Other AI Act provisions have earlier dates; do not say the entire law starts in 2027.
- **GDPR:** Regulation (EU) 2016/679; already applicable to personal-data processing, irrespective of AI Act timing.
- **DORA:** Regulation (EU) 2022/2554; applies to operational ICT risk and relevant third-party arrangements. It does **not** independently make web scraping of customer data lawful.

Primary texts:
- https://eur-lex.europa.eu/eli/reg/2024/1689
- https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32026R1744
- https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-113
- https://eur-lex.europa.eu/eli/reg/2016/679/oj
- https://eur-lex.europa.eu/eli/reg/2022/2554/oj

## 2. First legal question: what is this specific system used for?

**Never classify by “uses LLM” or “has human approval.”** Record the system's **intended purpose**, users, decision influence, data, deployment setting, provider/deployer identity, and version.

- **Annex III(5)(b):** AI intended to evaluate the **creditworthiness of natural persons** or establish their credit score is generally high-risk; explicit exception for AI used for detecting financial fraud.
- **Annex III(4):** Certain AI employment/recruitment use cases are high-risk.
- **Annex III(5)(c):** Risk assessment/pricing for **life and health insurance concerning natural persons** is high-risk.
- **Corporate/SME entity-only research:** Not automatically within the *natural-person* creditworthiness category, but other AI Act, privacy, security, and bank duties may still apply.
- **AML/KYC and back-office:** Not automatically high-risk merely because those labels appear, but intended use and other Annex III categories must still be assessed.
- **Article 6(3) filter:** Some Annex III systems may qualify for a narrow exception if legally assessed and documented; profiling of natural persons has special treatment. Do **not** assert that an assistant checking a credit file is exempt simply because a human clicks approve.
- **Agent Assurance itself:** Must undergo its own intended-purpose/risk-classification review. When materially influencing creditworthiness assessment it could fall within, or form part of, a high-risk use case. Approval and “only verification” are **not** automatic exemptions.

Official: https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-3 and https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-6

## 3. Provider vs deployer is consequential

A bank may be a **provider** for an AI system it develops/puts into service in its name, a **deployer** for a vendor or group system it uses, or have more complex roles. Roles depend on actual contractual and technical facts—not simply whether it “uses Claude.” A provider's documentation/logging design duties differ from a deployer's use/monitoring duties. Some modifications can change responsibilities; request legal evaluation rather than infer.

| Legal provision / topic | Broad obligation if applicable | What Agent Assurance can supply | What it CANNOT claim |
|---|---|---|---|
| **Art. 9 / 10** risk & data governance (high-risk provider) | Processes for managing risks and relevant data quality | Evidence of tested source/identity/freshness checks | Full risk-management program or bias validation |
| **Art. 11 / Annex IV** technical documentation (high-risk provider) | Defined technical system documentation | Tool trace, model/policy version, verification test results as supporting material | Complete Annex IV documentation |
| **Art. 12** logging (high-risk system) | Technical event-recording capability | Captured per-case events, provenance and trace gaps | That all required events exist across an external platform |
| **Art. 13** transparency to deployers | Provider supplies understandable info/instructions | Referenced limitations and claim rationale | Full provider obligations satisfied |
| **Art. 14** human oversight | High-risk systems designed to enable effective oversight | Plan approval, human intervention, stop/reject, reviewer trace | That a button alone makes oversight effective |
| **Art. 15** accuracy, robustness & cybersecurity | Appropriate high-risk system quality | Specific tested checks, denied-tool-call evidence | General safety/security certification |
| **Art. 26** deployer duties | Competent human oversight, use per instructions, monitoring, input relevance where controlled, log retention | Review actions, relevance checks, monitoring feed, controlled log records | Full deployer compliance or all log-retention requirements satisfied |
| **Art. 27** FRIA (scope-limited) | Impact assessment for certain deployers/use cases, including Annex III 5(b)/(c) | Draft evidence and links to human oversight | A completed or legally approved FRIA |
| **Art. 86** explanation right (scope-limited) | Explanation for certain affected persons | Source-linked review notes where appropriate | A legally sufficient decision explanation without human/Legal review |
| **Art. 50** transparency (separate scope) | Certain disclosures for interaction with AI / synthetic content | Optional visibility flags for client-facing interfaces | Blanket disclosure compliance |

Official article pages: https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-12 ; https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-14 ; https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-26 ; https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-27

**Log retention precision:** Article 26(6) addresses automatically generated logs **under a high-risk deployer's control**, generally at least six months unless otherwise provided by applicable law; financial-institution record arrangements apply. This is **not** permission to retain all raw prompts, documents, or sensitive data forever.

## 4. GDPR: independent, immediate constraint

Before processing personal data, ensure the responsible bank has documented a lawful basis and purpose. The verifier must **not** infer permission merely because the material is public or the employee approved the plan.

| GDPR concern | Engineering requirement |
|---|---|
| Art. 5 purpose limitation & minimization | Record purpose, allow only permitted fields and source classes; no scope expansion |
| Art. 5 accuracy | Identify conflicts/outdated records; do not automatically write corrections to source systems |
| Art. 6 lawful basis | Require bank-provided lawful-basis reference where personal data is processed; if absent, `LEGAL_REVIEW_REQUIRED` |
| Art. 9 special-category data | Block by default in MVP; require explicit policy + legal authorization for production scenarios |
| Art. 22 decisions based solely on automation | Never make or trigger a final credit/customer decision automatically; route to authorized process |
| Arts. 25, 32 privacy/security by design | Pseudonymize case IDs, limit retention, encrypt protected records, restrict access |
| Art. 35 DPIA when relevant | Link to existing DPIA assessment; do not invent one |

Sources: https://www.edpb.europa.eu/topics/key-gdpr-concepts/legal-basis_en and https://www.edpb.europa.eu/topics/key-gdpr-concepts/basic-principles_en . Web-scraping personal data requires separate careful review; public availability does not itself establish lawful use.

## 5. DORA and internal bank controls

DORA concerns ICT risk and external-provider governance, including resilience and relevant third parties. For this product, implement appropriate **tool inventory, dependency identifiers, failure logging, vendor/source policy, and incident handoff**, without claiming DORA mandates an MCP control layer.

Bank policy is its own binding execution constraint: tool allowlists, reviewer authority, approved business purposes, approved third-party sources, classification of data, and whether a task needs DPO/Compliance escalation. **Local deployment should integrate approved governance, not replace the RBI AICO.**

## 6. Policy knowledge base: versioned and citable

Minimum `PolicyRule` structure:

```json
{
  "rule_id": "POL-DATA-001",
  "title": "No unrestricted people-search for credit research",
  "source_uri": "bank-policy://demo/data-access/v3",
  "authority_type": "INTERNAL_POLICY",
  "version": "3.0",
  "effective_from": "2026-10-01",
  "owner": "demo-compliance",
  "applicability": ["customer_related_case"],
  "effect": "DENY",
  "match": {"tool": "unrestricted_web_search", "data_category": "PERSONAL_DATA"},
  "requires_human_review": false
}
```

**This is a synthetic example policy—not an actual Raiffeisen policy.** A real policy owner must approve its meaning. Maintain a separate legal reference index with official article links + version/effective-date metadata, never secretly rewrite rules via LLM.

### Legal preflight algorithm

1. Load verified AI system classification/role/purpose profile; missing => `LEGAL_REVIEW_REQUIRED` if relevant.
2. Load approved current bank rules + original sources; missing/expired => fail closed for affected actions.
3. Determine data categories and whether GDPR basis/consent/legal authority information is available; flag absent proofs.
4. Check each planned MCP tool/action/source against deterministic policy.
5. Annotate relevant AI Act duties as `APPLICABLE`, `NOT_APPLICABLE_WITH_REASON`, or `NEEDS_LEGAL_CONFIRMATION` **only when supported by system profile**; otherwise use `NEEDS_LEGAL_CONFIRMATION`.
6. Emit preflight outcome, restrictions, rule IDs, legal references, policy version, and reviewer/escalation requirement.
7. On execution, enforce the actual permitted calls; do not rely on preflight prose.

## 7. Generate an *evidence pack*, not an EU AI Act certificate

Each case report must have an **AI Act relevance section**:
- System name, version, intended purpose and assessed risk classification **or `UNCONFIRMED`**;
- Provider/deployer role **or `UNCONFIRMED`**;
- Article-to-evidence mapping where applicable; no broad legal conclusions;
- Original plan and revised approved plans with timestamps and identity of reviewers;
- MCP requests/results (or redacted references and hashes when privacy requires);
- Claim verification statuses and unresolved gaps;
- Human intervention and final signoff;
- `NOT_CAPTURED` artifacts and limits;
- “Prepared as supporting governance evidence; **not a certification or legal opinion**.”

**Legal checklist must be visible before plan approval**; attaching a report only at the end is not sufficient for the intended product.

## 8. Illustrative legal branches for demo

| Action | Preflight | Reason |
|---|---|---|
| Read synthetic corporate registry via approved demo MCP | `ALLOWED` | Demo policy explicitly allows public corporate fixture fields |
| Read synthetic licensed legal-status fixture | `ALLOWED_WITH_CONDITIONS` | Restrict to exact company ID and read-only action |
| Scrape arbitrary websites to profile a natural person | `BLOCKED` | MVP no source/data authorization; privacy risks |
| Access real personal credit data with no lawful-basis reference | `LEGAL_REVIEW_REQUIRED` | Applicable basis/use cannot be established |
| Approve a banking credit decision | `BLOCKED` | Outside product capability and scope |
| Read previously captured case evidence for initial assessment | Only if existing reviewer permission allows | Existing evidence is not an excuse to access unauthorized data |

## 9. Regulatory source update policy

- Date-pin the legal corpus and the policy configuration included with every report.
- Compare against official EUR-Lex/EU AI Act Service Desk and bank-approved updates **before production release**.
- Route disputed legal interpretations to Compliance; no agent can autonomously mark a law “fully satisfied.”
- Keep policy enforcement deterministic and testable; LLM retrieval is an analysis aid.

## 10. Context from EU banking supervision

The EBA's November 2025 mapping found no significant contradictions between AI Act and the EU financial-services rules it examined, but noted that **integration effort can still be needed**. Reuse of bank controls is sensible; building a parallel compliance bureaucracy is not the goal.

Official EBA report: https://eba.europa.eu/sites/default/files/2025-11/d8b999ce-a1d9-4964-9606-971bbc2aaf89/AI%20Act%20implications%20for%20the%20EU%20banking%20sector.pdf

## Legal review caveat

This is an engineering research brief, not legal advice. The precise classification, national competent authority, data-law basis, provider/deployer role, retention rules, permitted tools, and documentary obligations must be validated for **each actual deployment** with legal/compliance owners. In the hackathon, use only synthetic data and clearly labeled demo policies.
