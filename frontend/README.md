# frontend/

The review UI: plain HTML, CSS and JavaScript, no build step, no framework, no npm. FastAPI serves it at `/` (page) and `/static/` (files). All state lives in the backend; the browser only renders what `GET /cases/{id}` returns and sends the reviewer's decisions.

| File | What it does |
|---|---|
| `index.html` | The page skeleton: sidebar, top bar with the demo modes, the case workspace (progress stepper, story, claims panel, safeguards, history), a slide-over panel |
| `app.js` | The case screen. Reads one case top to bottom as a story: the AI's finding, the claims with verdict stamps, each plan version with its automatic policy check and the reviewer's decision, what the agent checked, the sign-off and the evidence pack. Only the current step is open and has one main action |
| `okr.js` | The shell around the case: navigation, overview, job pages, hash routes (`#/`, `#/job/J1`, `#/case/S01/J1`), the "Watch the demo" and "Do it yourself" modes, and the progress checklist |
| `style.css` | Design tokens and layout (Inter font, yellow and black palette, responsive down to phone width) |

## How it talks to the backend

- `api(path, opts)` in `app.js` wraps `fetch`, adds the `X-Reviewer-Id` header of the user chosen in "Acting as", and turns HTTP errors into short messages.
- After each action the page re-reads the case view and re-renders. There is no client-side copy of verdicts, plans or approvals that could drift from the server.
- Approve sends the exact `plan_hash` the reviewer looked at; if the stored plan changed, the backend refuses.

## Jobs to be done (`okr.js`)

The sidebar groups the scenarios under five jobs a reviewer would hire the product for. Each job has an objective and key results that tick themselves from the case record as you click through:

| Job | Shown with |
|---|---|
| J1 Verify the claims | S01, S05, S04, S03, S08-OK |
| J2 Approve the plan first | S01, S06, S09 |
| J3 Lawful sources only | S07, S07-OK, S07-HOL, S07-WD, S08, S09 |
| J4 Break-ins and failures | S01-INJ, S08, S02, plus the safeguard buttons |
| J5 Evidence pack for audit | S01, S05 |

`okr.js` never calls the API and never changes a verdict, a preflight result or a decision: it only reads and renders. The session checklist is kept in `sessionStorage`; "Reset demo" clears it.

## Safeguard buttons

"Test the safeguards" sends requests straight to the gate through `POST /cases/{id}/redteam/attempt-tool`, like a misbehaving agent: an open web search, a call caused by document text, a lookup of a different company. Each one comes back `DENIED` with the rule id and zero tool invocations. "Make the court registry time out" sets a fail mode, so the claim ends `INSUFFICIENT_EVIDENCE`. "Stop this case" revokes every approval.

## Text and branding

Plain-language labels for tools and states are in `app.js` (`TOOL` and the vocabulary block), so the reviewer sees "Licensed court-case registry" rather than `legal_case_status_lookup`. The UI uses no Raiffeisen logo and says in the footer that it is not a Raiffeisen product.
