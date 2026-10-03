# Karyakarta: USP and the AI Teammates

*Team Genesis51 · Track 3: Autonomous AI Teammates · Paytm Build for India AI Hackathon, Mumbai*

> **Pitch line:** "Every payment company automates the easy 80%. Karyakarta automates the hard 20%: the company cases
> that end up in manual review."

---

## 1. Our USP in one paragraph

Karyakarta is an AI teammate for the Key Account Manager that **does the document work of corporate onboarding end to end**:
it reads every document, checks them against each other, traces ownership through other companies to find every
beneficial owner above 10%, remembers the merchant as a knowledge graph, and chases the merchant in Hindi by voice. The
KAM opens a case that is already read, checked and explained, and spends time only on the part that needs a human:
**the decision**. And the AI is **structurally unable to make that decision**: code checks, a person approves.

### The six things that make it different

| # | USP | Why it matters | Proof in the prototype |
|---|---|---|---|
| 1 | **It targets the hard 20%**: layered ownership and signatory questions that automated checks leave to manual review | This is the slowest, costliest part of onboarding, and where merchants stay capped longest | Hidden **18%** owner found behind Sharma Holdings LLP; signatory who is not a current director caught |
| 2 | **No AI decides pass or fail.** The model reads, **code checks**, the model explains, a human approves | Repeatable, explainable, auditable: what a regulated payments business needs | 10 deterministic rules, evidence on every result; the API refuses approvals from the agent (HTTP 403) |
| 3 | **Every finding is one click from its evidence** | A KAM can trust or overrule a finding in seconds instead of re-reading the file | Click a finding to open the PDF at the exact field; 47 of 51 hero fields located with page boxes |
| 4 | **Merchant Digital Twin**: a Cognee knowledge graph per merchant that anyone can question | Layered ownership is a graph problem; the same record can later watch the merchant after go-live | "Who owns more than 10%?" answered with its source document; call history is searchable too |
| 5 | **A Hindi voice agent that resolves, not just rejects**, and is safe by design | Cold rejection emails cause the round trips; a clear call in the merchant's language fixes them | Live agent verified: refuses OTPs, makes no promises, never raises KAM-only issues, switches language |
| 6 | **India-native and honest by construction** | Sarvam for Indic documents and voice; PAN/GSTIN/CIN/IFSC/FSSAI logic; DPDP and RBI aware design | Failures are shown, never faked; mocks are labelled; the status matrix says what is not built |

### What the status quo looks like (and our difference)
| Typical automation | Karyakarta |
|---|---|
| OCR plus rules for simple, single-owner cases | Same, plus look-through ownership and signatory authority |
| Complex cases fall into an email and WhatsApp loop | The case arrives with findings, evidence and a drafted chase |
| A black-box score or a chatbot answer | Deterministic rules with evidence; the model only reads and explains |
| One decision maker or none | Maker and checker, with the agent excluded by the server |
| Rejection reason as text | A call in Hindi that explains exactly which document to send |

---

## 2. The AI teammates

Karyakarta is a small team, not a chatbot. Each teammate has a job, tools, a hand-off and a hard limit. The orchestrator
makes them one workflow.

```
 Merchant uploads ──► 1 ORCHESTRATOR (n8n) ──► 2 READER ──► 3 VERIFIER ──► KAM decides ──► Compliance decides
                              │                                  ▲
                              ├──────► 4 DIGITAL TWIN ◄──────────┘ (answers the KAM's questions)
                              └──────► 5 VOICE CHASER ──► Merchant (Hindi)
```

### 1. The Orchestrator (n8n): "the chief of staff"
* **Job:** runs the whole pipeline the moment documents arrive: extract, store memory, build the graph, cross-check, route.
* **Tools:** two n8n workflows (37 nodes) with native Cognee nodes; calls the backend by HTTP.
* **Autonomy:** fully autonomous from upload to routed case. Failures never stop a batch.
* **Never:** approves, rejects, or talks to the merchant.
* **Proof:** 8 documents routed to ESCALATE in about 108 seconds with no human step.

### 2. The Reader (Sarvam Document Intelligence): "the one who reads every page"
* **Job:** classifies each document, extracts its fields with a confidence score, and locates each value on the page.
* **Tools:** Sarvam extract (schema per document type) and digitise (layout boxes).
* **Autonomy:** fully autonomous.
* **Never:** decides anything. Every value carries confidence, page and box so a human can verify it.
* **Proof:** 51 fields from 8 documents, 47 located on the page; CRM form 20 of 20 filled.

### 3. The Verifier (rules in Python): "the one who checks everything against everything"
* **Job:** runs 10 cross-document checks: name consistency, PAN type, GSTIN contains PAN, CIN, signatory is a current
  director, beneficial owners above 10% through other entities, bank holder against legal name and penny-drop, address
  drift, required documents, licence validity. Then routes the case **AUTO / ASK / ESCALATE**.
* **Tools:** deterministic code and a (mock) MCA / GST / bank record. **No LLM.**
* **Autonomy:** fully autonomous, and fully repeatable.
* **Never:** guesses. Each result lists evidence (document, field, page, value).
* **Proof:** finds all 4 planted problems on Sharma Foods and attaches evidence to each.

### 4. The Digital Twin analyst (Cognee): "the one who remembers the merchant"
* **Job:** builds a knowledge graph of the merchant from all documents and calls; answers the KAM's questions with sources.
* **Tools:** Cognee Cloud (graph, vector search, graph completion with Cognee's own model), via native n8n nodes.
* **Autonomy:** builds memory autonomously; answers on request.
* **Never:** decides pass or fail. If it is down, every other teammate keeps working.
* **Proof:** "Who owns more than 10%?" returns Rakesh Sharma 18% via the LLP, citing the shareholding declaration.

### 5. The Voice Chaser (Sarvam Samvaad): "the one who calls the merchant"
* **Job:** explains in Hindi what the merchant must fix and which document to send; agrees a time; the outcome and transcript
  go back onto the case and into the merchant's memory.
* **Tools:** a Sarvam voice agent fed by the live case (only items the merchant can fix), triggered through n8n.
* **Autonomy:** acts on its own **once triggered**. Today the KAM clicks Voice Chase; an automatic trigger on the ASK route
  is a one-branch change in n8n.
* **Never:** discusses items that need the KAM's judgement, accepts OTPs or card/account numbers, or promises approval.
* **Proof:** seven scenarios against the live agent, including the OTP refusal, "when will I be approved?" and a wrong number.
* **Honest status:** the Send Voice Chase button now places a real outbound call (Sarvam over a connected Twilio number) and follows it to the transcript. The first real call to a merchant's phone has not been made yet; the agent itself is verified with a scripted merchant.

### The people (decision makers)
* **KAM (maker):** reviews, overrules any finding, approves and forwards. Sees one-click approval on AUTO cases and full
  evidence on ESCALATE cases.
* **Compliance (checker):** the four-eyes approval after the KAM submits.
* The server enforces it: the agent and the merchant get **403** on approve, submit and send back; compliance can act only
  after the KAM has submitted.

---

## 3. Autonomy at a glance

| Level | Meaning | Where it applies here |
|---|---|---|
| A0 | Human only | **Approving, rejecting, sending back, overruling a finding** |
| A1 | AI suggests | The KAM's CRM overrides (AI value kept next to the human's) |
| A2 | AI acts when a person triggers it | **Voice Chase** (KAM click today) |
| A3 | AI acts on its own within guardrails | **Reading, extracting, cross-checking, routing, building memory, drafting the chase, writing the audit trail** |
| A4 | AI decides on its own | **Deliberately not used** |

---

## 4. Why this is a teammate and not a chatbot

A chatbot waits for a question. When a merchant uploads eight documents, **nobody asks Karyakarta anything**, and it still:

1. classifies and reads all 8 documents (51 fields) and shows where each value sits on the page;
2. runs 10 cross-document checks and finds 4 problems, each with evidence;
3. works out that a hidden shareholder owns 18% and has no KYC;
4. fills a 20-field CRM form with a citation per field and flags 2 conflicts;
5. builds a knowledge graph of the merchant so the KAM can ask questions;
6. drafts the Hindi explanation for the merchant and tells the KAM what it will and will not say;
7. routes the case (AUTO / ASK / ESCALATE) and writes every step to an append-only audit trail.

The KAM then spends their time on **two decisions** (the signatory and the hidden owner), not on re-reading documents.

### Mapping to Track 3
| What Track 3 asks | What we show |
|---|---|
| AI that does real work | Reading, checking, ownership tracing, form filling, memory, merchant communication |
| Alongside people | Maker and checker stay human; every hand-off is explicit |
| Not just a chatbot | Ask this case is one feature among ten; the value is in the work done unprompted |
| Trust and guardrails | No AI pass/fail, server-side approval guard, voice safety rules, evidence on every finding |
| Observability | Append-only timeline of every AI and human action |

---

## 5. Pitch material

### 30 seconds
"Onboarding a company to Paytm's gateway means a KAM manually checking names, signatories and hidden owners across eight
documents, over emails and calls, while the merchant sits at a ₹50,000 cap. Karyakarta is an AI teammate that does that document
work: Sarvam reads the documents, plain code checks them, Cognee remembers the merchant as a graph, and a Hindi voice agent
chases what the merchant can fix. n8n runs it. It never decides: the model reads, code checks, the model explains, a human
approves. Every payment company automates the easy 80%. We automate the hard 20%."

### Demo flow (about 5 minutes)
1. **Merchant:** drop the 8 Sharma Foods documents in one go (hashes appear).
2. **KAM dashboard:** the case moves live; about 2 minutes later it is **ESCALATE**.
3. **Case page:** the 10 checks; open the signatory finding and the hidden-owner finding; each opens the source.
4. **Evidence viewer:** click a value, see the box on the real PDF.
5. **CRM form:** 20 of 20 filled, citations, two conflicts.
6. **Ask this case:** "Who owns more than 10%?" with the source.
7. **Voice Chase drawer:** the exact opening line, what the agent will ask, what is held back for the KAM, the number box.
   Press **Call now** with your own phone number and take the call. If you have not tested a real call before the demo, show the
   **voice call history** from a rehearsal instead and label it a rehearsal with a scripted merchant.
8. **Four-eyes:** as KAM, press *Approve & Forward* (it asks for confirmation on an ESCALATE case), then switch to the
   Compliance persona and approve. If you switch first, the server refuses with "Compliance can act only after the KAM has
   submitted the case": that refusal is itself worth showing.
9. Close on the pitch line.

Before presenting: `seed.bat --reset`, then `seed.bat --reset --hero-docs` for a safe fallback, and do one browser
walkthrough (the evidence viewer has not been checked in a real browser).

### What not to claim
* Real MCA21 / GSTN / CKYCR integration (registries are a labelled mock).
* A phone call to a real merchant until you have made one (the agent is verified with a scripted merchant; calling is built and tested but the first real call has not been placed).
* Hours saved or accuracy percentages (no baseline was measured).
* DPDP consent capture or user authentication in the backend (not built).
* Day-100 monitoring (it is the roadmap, built on the same merchant graph).
