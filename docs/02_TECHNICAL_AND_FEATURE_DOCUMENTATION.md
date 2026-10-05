# Karyakarta: Technical and Feature Documentation

*Team Genesis51 (Ritika Iyer, Samridhi Raj Sinha) · Paytm Build for India AI Hackathon, Mumbai · Track 3: Autonomous AI Teammates*

Everything here describes what exists in the repository. Where something is mocked or not built, it says so. Numbers
were measured on the development machine on 2026-10-02 unless stated otherwise. All demo data is synthetic.

Contents: 1 Status · 2 Stack · 3 Features by persona · 4 Pipeline · 5 Cross-document checks · 6 CRM auto-fill ·
7 Digital Twin (Cognee) · 8 Voice Chase (Sarvam) · 9 n8n workflows · 10 Audit and live updates · 11 Security and
compliance posture · 12 Reliability · 13 API · 14 Data model · 15 Configuration · 16 Testing · 17 Performance ·
18 Limitations and roadmap · 19 Repository and running it

---

## 1. Scope and honest status

**The problem.** Non-individual merchants (companies, LLPs, partnerships, trusts) go live on Paytm's payment gateway with
only PAN and a bank account, capped at ₹50,000 a month. Lifting the cap needs a full document set. Someone must check
names across documents, that the signatory is a current director, every beneficial owner above 10% (through other
companies), the bank account against the legal name, and addresses. Today the KAM does this by hand through emails,
WhatsApp and calls. A mismatch found late costs another round trip while the merchant stays capped.

**The solution.** Karyakarta is an AI teammate for the KAM that does the document work so the KAM only decides.
Principle: *the model reads, code checks, the model explains, a human approves.*

| Capability | Status | Notes |
|---|---|---|
| Document upload, hashing, type detection | **Built, tested** | PDF/JPG/PNG up to 25 MB, SHA-256, 9 document types |
| KAM can delete a submitted file; demo reset of a case | **Built, live-verified with Cognee** | Delete re-runs the checks and removes the file's items from the merchant twin; locked once the case is with Compliance |
| Realistic demo document pack (9 documents + 4 fixes) | **Built; the 9 documents are recorded live, the 4 fixes are not read yet** | `seed/make_realistic_docs.py`, watermarked specimens; see `07_DEMO_RUNBOOK.md` |
| Field extraction with confidence and page location | **Built, live-verified** | Sarvam Document Intelligence; 51 fields on the 8-document hero case |
| 10 cross-document checks + AUTO/ASK/ESCALATE routing | **Built, tested** | Plain Python, evidence on every result |
| Beneficial-owner look-through (>10%) | **Built, tested** | Through a company/LLP shareholder using the declared partner table |
| Auto-filled CRM form with citations and conflicts | **Built, tested** | 20 fields; overrides are audited |
| PDF evidence viewer with bounding boxes | **Built** | Not exercised in a real browser during testing (pdf.js cannot run in the test environment) |
| Merchant Digital Twin (Cognee graph) + Ask this case | **Built, live-verified** | Cognee Cloud, one dataset per case |
| n8n orchestration with native Cognee nodes | **Built, live-verified** | 4 workflows, 75 nodes |
| **Settlement Agent** (post-onboarding) | **Built, live-verified on a synthetic ledger** | Settlements tab on Case Detail, deterministic thresholds (>150% volume, >10% mismatch), MONITOR → RECONCILE → INVESTIGATE → CREATE CASE → ESCALATE through n8n, Cognee recall and store, Sarvam brief with verified numbers; opens an investigation case in the KAM queue. No real acquirer feed, no money movement, no scheduler. See `06_SETTLEMENT_AGENT.md` |
| **Drishti: contact point verification** (stage 6) | **Built, live-verified with synthetic photos** | Secure camera-only link, five checks, autonomous `CPV_VERIFIED` only on four hard checks. Real Sarvam signboard reading and transliteration verified; capture page tested with fake browser APIs, **not on a real phone** |
| Drishti evidence card (KAM) and the merchant's link card | **Built, tested** | Link and QR in the AI Communication Center instead of WhatsApp |
| **V-CIP preparation** (stage 7) | **Built; the second voice agent is not tested** | Randomized Hindi questions, officer card, one-click sign-off. **No face matching.** Needs a second Sarvam agent (`SARVAM_VCIP_AGENT_ID`) |
| Hindi voice agent (Sarvam Samvaad) | **Agent verified live** | 7 scenarios with a scripted merchant over a call session |
| Voice call history, transcript, memory of calls | **Built, verified** | Via rehearsal calls through n8n into Cognee |
| Maker / checker with server-side role and stage guard | **Built, tested** | Roles, not user accounts |
| Append-only audit trail + live event stream | **Built, tested** | SSE |
| MCA21 / GSTN / bank penny-drop | **Mock** | `app/registry/mock_registry.py`, clearly labelled |
| WhatsApp / email chase | **Not sent** | The action is recorded on the timeline only |
| Outbound phone call to the merchant (Sarvam Instant Outbound over a connected Twilio number) | **Built, no real call placed yet** | Button, validation, n8n place-and-poll, result recording are tested; the exact Sarvam request was checked by a dry run. The first real call is still to be made |
| DPDP consent capture in the backend | **Not built** | The portal shows consent controls and the statutory text; nothing is stored |
| CKYCR lookup | **Not built** | |
| Day-100 transaction monitoring | **Not built** | Roadmap: same merchant graph plus a transaction feed |
| Stages 8 to 10 (settlement test, e-agreement, live) | **Labels only** | No integrations |
| Authentication / user accounts | **Not built** | The OTP login screen is a UI mock |

---

## 2. Technology stack

| Layer | Technology |
|---|---|
| Frontend | React 18.3, Vite 5.4, TypeScript 5.5, Tailwind 3.4, pdf.js 4.10 (evidence viewer), lucide-react; Vitest 2 + Testing Library for tests |
| Backend | Python 3.11, FastAPI 0.142, Uvicorn 0.54, SQLModel 0.0.47 / SQLAlchemy 2.0, Pydantic 2.13, httpx 0.28 |
| Storage | SQLite in WAL mode (6 tables), files under `storage/<case>/`, `demo_cache/` of recorded Sarvam results |
| Orchestration | n8n 2.41.6 in Docker, community node `n8n-nodes-cognee` 0.7.0 (native Cognee nodes) |
| Document AI | Sarvam Document Intelligence via `sarvamai` 0.1.35: schema-based extraction + layout digitisation |
| Voice AI | Sarvam Samvaad agent via `sarvam-conv-ai-sdk` 1.1.1 (call agent, Hindi); Sarvam speech-to-text and text-to-speech used by the test probe |
| Memory | Cognee Cloud (knowledge graph, vector search, graph completion with Cognee's own LLM) |
| Image checks | Pillow and numpy (screen-replay heuristic), OpenStreetMap Nominatim (geocoding), qrcode (QR for the merchant link) |
| Test data | `reportlab` generates the synthetic Sharma Foods PDFs (byte-identical on every run); `seed/make_shop_photos.py` makes printable synthetic shop images |

**Which model answers "Ask this case"?** Cognee's: the backend calls Cognee's search with `GRAPH_COMPLETION` and Cognee
writes the answer. Sarvam is used to read documents and to speak, not to answer case questions.

---

## 3. Features by persona

### Merchant signatory
* Branded login and a Stage 1 dashboard showing *Account live, capped ₹50,000/month* and the upgrade call to action.
* Account Center with the DPDP consent controls and the statutory consent text (UI only, see section 18).
* **Document upload:** five requirement cards (business proof, bank details, tax/GST, signatory KYC, and a new
  *Company & Governance* card for incorporation certificate, board resolution, shareholding declaration, FSSAI). Click or
  drag-and-drop; each file shows its **SHA-256** and the type Karyakarta detected; rejected files are dropped with the reason.
* **AI Communication Center:** the live, merchant-fixable issue found in their documents (not a canned message).

### KAM (maker)
* **Pipeline dashboard:** 5 live KPI cards (open, pending AI verification, awaiting merchant, ready for submission,
  escalations), a case table with stage, document progress, AI flags, route badge (AUTO / ASK / ESCALATE) and SLA timer.
  Updates live as documents are processed.
* **Case workspace:** merchant header, 10-stage tracker, the **10 cross-document checks**, each marked *Merchant can fix* or
  *Needs human judgement*, with clickable evidence that opens the source document with the field highlighted;
  uploaded/missing checklist; append-only timeline.
* **Interactive PDF evidence:** the real PDF with every extracted value boxed on the page, a field list with confidence,
  click-to-highlight both ways, zoom and paging. Tables are boxed at table level; values that could not be located show "not located".
* **Auto-filled CRM form:** 20 fields with a citation per field (for example *Source: GST Cert p.1*), confidence, conflict
  notes, and an override mode whose edits are audited (the AI's original value is kept).
* **Ask this case:** type a question ("Who owns more than 10%?") and get an answer with the source documents.
* **Voice chase:** a drawer that previews the exact opening line, what the agent will ask for, and what is held back for the
  KAM; sends the chase; the case then shows a **voice call history** with outcome, summary, transcript and whether it is in
  the case memory.
* **Approve and forward:** asks for confirmation on an ESCALATE case.

### Merchant: shop verification (stage 6)
The **AI Communication Center** shows a *Verify your shop* card with a secure link, a QR code and the two photos to take (no WhatsApp message). The link opens a camera-only capture page: no
gallery picker, a live camera, high-accuracy GPS and bearing on every photo, then a clear outcome. Full detail in `05_DRISHTI_CPV_AND_VCIP.md`.

### Compliance (checker)
* The same workspace with the checker's actions: *Send back* and *Approve (Compliance)*. The API allows them only after the
  KAM has submitted the case (stage 5) and only for the compliance role.
* At stage 6 the KAM sees the **Drishti card** (photos with GPS and bearing, the five checks, distance, the signboard text read, approve after review or ask for new photos). At stage 7 Compliance sees the
  **V-CIP card** (randomized questions with expected answers, the pre-interview transcript, the owner selfie and the ID document side by side, one-click sign-off, and a note that face matching is not automated).

---

## 4. The document pipeline in depth

### 4.1 Upload and type detection
`POST /api/cases/{id}/documents` accepts multiple files. Each is validated (extension, size, not empty), hashed (SHA-256),
stored, and classified. Classification uses, in order: the merchant's chosen slot, filename hints and regular expressions,
and, if still unknown, a keyword classifier over the OCR text. A KAM can correct a type (`POST /documents/{id}/type`). The
call returns `202` immediately; processing is asynchronous.

### 4.2 Extraction (Sarvam Document Intelligence)
One **schema per document type** tells Sarvam which fields to return. Eight types:

| Type | Fields |
|---|---|
| Company PAN | PAN number, holder name, father's name, date |
| GST certificate | GSTIN, legal name, trade name, constitution, principal place address, dates, registration type, validity |
| Certificate of Incorporation | CIN, company name, date of incorporation, company type, registered office, registrar |
| Board resolution | company, CIN, date, purpose, authorised signatory name and designation, list of signatories |
| Cancelled cheque | account holder, account number, IFSC, bank, branch, account type |
| Director KYC | name, ID type, masked Aadhaar, PAN, DIN, date of birth, address |
| Shareholding declaration | company, as-of date, shareholders (name, type, %), entity partners (look-through table) |
| FSSAI licence | licence number, business name, premises address, type, kind of business, validity |

Each value comes back with a **confidence** and a **page number**. The result is normalised into one field model.

### 4.3 Locating values on the page (the evidence boxes)
Sarvam's extraction returns **no coordinates**. A second pass, *digitise*, returns layout blocks with normalised boxes.
Each extracted value is matched to a block (substring match, then fuzzy match at ratio 0.88). Tables are boxed at **table
precision**, because Sarvam gives no cell coordinates and interpolating rows would be guesswork. Values with no match get
no box and show "not located". On the hero case: **47 of 51 fields are located**; box precision is `block` or `table`.

### 4.4 Per-document checks (run during extraction)
GSTIN and CIN format, IFSC format, FSSAI number, masked Aadhaar, shareholding total (must equal 100%), account type.
A failed per-document check marks the document "needs attention" with the reason.

### 4.5 Rate limiting and failure handling
Sarvam allows about 10 job submissions a minute. A sliding-window limiter (9 per minute, 3 in flight) queues the rest, with
retries and backoff and a 180 s timeout. Errors are turned into readable messages (for example *Sarvam rejected the file
(HTTP 400): INPUT_INVALID…*), never raw HTTP dumps.

### 4.6 Demo cache
Sarvam results are stored by file hash. With `DEMO_MODE=true` (or on a live failure) the recorded result is served, so the
demo survives a network outage and costs no API calls. `seed.bat --refresh-cache` re-records it.

### 4.7 A lesson in confidence
During testing Sarvam read a cheque's account number as `500034928174` instead of `50200034928174` **at 100% confidence**
(a "CANCELLED" stamp covered digits). Confidence alone cannot catch this. Karyakarta compares the cheque number with the bank's
penny-drop record and raises the discrepancy; the synthetic cheque was also re-laid-out so the stamp no longer covers data.

---

## 5. The 10 cross-document checks

Plain Python in `app/checks/cross_check.py`. Pure functions: documents + application + registry in, checks out. Every
result is `{id, label, status, detail, evidence, action}`, where evidence lists `{document, field, page, value, source}`.
Status is `pass`, `fail`, `warn` or `skip`; `action` is `ask` (the merchant can fix it) or `escalate` (needs human judgement).

| # | Check | What it verifies | Failure routes to |
|---|---|---|---|
| 1 | Legal name consistent | Application, PAN, GST, COI and cheque names match (case, punctuation, Pvt/Private and Ltd/Limited ignored) | ask |
| 2 | PAN valid and matches entity type | `AAAAA9999A` format; 4th character matches the entity (C company, F firm/LLP, P individual/proprietor, T trust); equals the application PAN | ask |
| 3 | GSTIN embeds the PAN | Valid 15-character GSTIN; characters 3 to 12 equal the PAN; Active in the GST registry | ask |
| 4 | CIN valid and matches | 21-character CIN; equals application and MCA record; MCA status Active. Skipped for LLP, partnership, proprietorship | ask |
| 5 | Signatory is a current director | The board-resolution signatory is in the MCA director list | **escalate** |
| 6 | Beneficial owners above 10% identified and KYC'd | Look-through ownership; every owner above 10% needs KYC on file; declaration must match the registry | **escalate** when hidden behind an entity or the registry differs; ask otherwise |
| 7 | Bank holder matches legal name | Holder name must match **exactly** (a missing "Private Limited" fails); current account, not savings; account number equals the penny-drop record | ask |
| 8 | Address consistent | COI registered office vs application; GST principal place vs the application's operating address and the GST registry; FSSAI premises vs GST | ask |
| 9 | Required documents present | The set required for this entity type and industry (the industry licence is reported by check 10) | ask |
| 10 | Industry licence present and valid | Present, not expired, issued to the company. **Only food / FSSAI is configured today**; other industries have no licence rule yet | ask |

**Name matching** has three tiers: *same* (case, punctuation, Pvt vs Private), *suffix* (equal once Private/Limited/LLP are
dropped, e.g. "Sharma Foods" vs "Sharma Foods Private Limited") and *different*. The general name check is lenient about
suffixes; the bank check is strict, because the settlement account holder must match exactly.

### 5.1 Beneficial-owner look-through (the hard 20%)
For every shareholder that is itself a company or LLP, the declared partner table is used to compute each person's
**effective** ownership. The Sharma Foods example:

| Shareholder | Holding | Result |
|---|---|---|
| Anil Sharma (individual) | 40% | 40% direct |
| Priya Sharma (individual) | 30% | 30% direct |
| Sharma Holdings LLP | 30% | Rakesh Sharma 60% of 30% = **18%**, Meera Sharma 40% of 30% = **12%** |

Rakesh Sharma (18%) and Meera Sharma (12%) are both above 10% and have no KYC on file, so the case escalates. Exactly 10%
is not above the threshold (tested). A corporate shareholder without a partner table is flagged as "no look-through".

### 5.2 Triage
`ESCALATE` if any failed check has action `escalate`; else `ASK` if any check fails or warns; else `AUTO`. The result sets
the case route, status and stage (4, KAM review), writes one audit event per issue, and a plain-language summary
(for example *4 issues found, 6 checks passed: 2 need human judgement (…) and 2 the merchant can fix (…)*).

### 5.3 The hero case result (Sharma Foods)
| Planted problem | Found by | Route |
|---|---|---|
| Cheque says "Sharma Foods", legal name is "Sharma Foods Private Limited" | check 7 | ask |
| Board-resolution signatory (Ravish Sahay) is not a current director (MCA: Anil Sharma, Priya Sharma) | check 5 | escalate |
| Hidden 18% owner behind Sharma Holdings LLP | check 6 | escalate |
| GST says Navi Mumbai, application says Mumbai | check 8 | ask |

Result: 6 checks pass, 4 fail, route **ESCALATE**. Each finding links to the exact document, field and page.

---

## 6. Auto-filled CRM form

`app/crm_form.py` builds the form by comparing extracted values with the merchant's application values. Three sections:
Business details (7 fields), Tax and banking (7), Stakeholders (6). For the hero case: **20 of 20 filled, average
confidence 100% (Sarvam-reported), 2 conflicts** (bank holder name, principal address). Each field carries:
source citation, confidence, a link to open the source document with the field highlighted, and a conflict note where two
sources disagree. Conflict rules include containment for addresses (one address containing the other is not a conflict).
KAM overrides are stored in `CrmOverride` with the AI's original value, and written to the audit trail.

---

## 7. Merchant Digital Twin (Cognee)

**What it is.** One Cognee dataset per case (`case_<slug>`) holding a knowledge graph built from the merchant's documents
and voice calls: people, companies, ownership, addresses, accounts, conversations.

**How it is fed.** For each document the backend produces a structured summary of the extracted fields and the check
results. n8n stores that text with the native Cognee node (**Memory > Remember**, background mode, unique file name
prefix `doc-<id>`), then runs **Cognify** once per batch to build the graph. Voice calls are stored the same way
(`call-<id>`).

**Why Remember with a unique prefix.** Cognee Cloud refuses an upload that re-uses a file name with different content
(HTTP 409 `DocumentUpdateRequiredError`), and the Add operation always names its file `text-1.txt`. Verified by test: three
different texts named `text-1.txt` store the first only; unique names store all three.

**Source links.** Remember in background returns no data ids, so after the graph build n8n lists the dataset's items
(Dataset > Get Data Items) and reports `{id, name}` to the backend, which maps names back to documents. That is how an
answer can name `Shareholding_Declaration.pdf` as its source.

**Ask this case.** `POST /cases/{id}/ask` runs a Cognee graph-completion search, maps data ids to documents, and returns
the answer with its sources. Verified answers include *who owns more than 10%* (Rakesh Sharma 18% via the LLP), *the GSTIN*
(with the GST certificate as source) and *what the merchant said on the voice call*. Saved answers are served when memory is
unavailable in `DEMO_MODE`.

**What it never does.** Cognee never decides pass or fail. If Cognee is unreachable, every other feature keeps working.

---

## 8. Voice Chase (Sarvam Samvaad)

### 8.1 What the agent is told
`GET /cases/{id}/voice-chase/context` builds the agent's variables from the **live checks**: contact name, merchant name,
number of items, the items in plain Hindi and English, the documents to send, and where to upload. It sends **only items the
merchant can fix** (checks with action `ask`, plus missing documents). Checks that need a KAM decision (signatory,
hidden owners) are returned separately as `held_back_for_kam` and **never reach the agent**.

### 8.2 The agent (configured in the Sarvam console)
Prompt rules: speak Hindi by default and switch language to the merchant's; short turns; only the listed items; **never**
promise approval, limits or timelines; **never** ask for or accept OTPs, PINs, card numbers or full account numbers;
documents only via the app; hand anything else to the account manager.

### 8.3 Verified behaviour (live agent, scripted merchant, 2026-10-02)
The agent is deployed for voice calls, so it hears audio. The probe `scripts/voice_agent_probe.py` plays the merchant with
Sarvam text-to-speech over a real call session using the actual case variables, and reads the agent's replies back with
speech-to-text.

| Scenario | Observed |
|---|---|
| Opening | Greets with the contact, business name and number of items from the variables |
| Merchant agrees | Explains both items and the next step |
| Merchant is busy | Asks for a callback time |
| Merchant asks for English | Switches to English (once re-asked identity) |
| "When will my account be approved?" | Makes no promise; says the account manager will explain |
| Merchant offers an OTP | Refuses; documents only through the app's Account Center |
| Wrong number | Apologises and ends the call |
| Asks about the signatory issue (held back) | Does not discuss it; defers to the account manager |

These are not real calls to a real merchant. The Hindi/Hinglish range was not stress-tested beyond these scenarios.

### 8.4 Call records
Every call result becomes a `VoiceCall` record (outcome, summary, transcript, Sarvam interaction id, memory status),
appears on the case's **Voice chase history**, writes a timeline event, and is stored in Cognee so the KAM can ask what the
merchant said. Outcomes: reached, promised upload, callback requested, no answer, busy, wrong number, failed, not placed.

### 8.5 Placing the call (Sarvam Instant Outbound)
Pressing **Call now** in the Voice Chase drawer (number box prefilled from the case, validated as an international number,
button names the number it will call) does this:
1. The backend validates the number, blocks a second call while one is in progress, stores the number on the case and
   hands `{case_id, to_number}` to n8n. The timeline shows the number masked.
2. n8n gets the agent context and calls the backend, which sends **one request to Sarvam** (`POST …/outbounds`): your
   agent, the connected Twilio number as the caller, the live case variables and the Hindi opening line.
3. n8n waits and polls every 15 seconds (up to 15 minutes) until Sarvam reports the call ended. **No public URL is
   needed**: the result is read from Sarvam's attempts and transcripts APIs. (`SARVAM_CALLBACK_URL` can optionally give Sarvam a
   webhook instead.)
4. The outcome (reached, no answer, busy, failed), duration and the transcript are recorded on the case, stored in Cognee
   and shown in *Voice chase history*. A call that cannot be placed is recorded as *Voice call not placed* with Sarvam's reason.

**Status:** tested with Sarvam mocked, the polling and transcript parsing checked against real Sarvam data from earlier
sessions, and the exact request verified by a dry run. **No real call has been placed yet.** Things that can still differ on
the first call: the agent *version* (set to 1), whether the Twilio account may call the destination country (a trial account can
usually call only verified numbers), and Sarvam's status vocabulary for unanswered calls. Each of these shows up as a readable
reason on the case timeline.

---

## 9. n8n workflows

### 9.1 Karyakarta - Document pipeline (20 nodes, `POST /webhook/karyakarta-documents`)
| Step | Node | What it does |
|---|---|---|
| 1 | Documents uploaded (webhook) | Receives `{case_id, doc_ids, dataset}` |
| 2 | Settings, Split out documents, Loop over documents | One document at a time |
| 3 | Extract + check (Sarvam via backend) | `POST /documents/{id}/extract`; error output goes to *Mark extraction failed* |
| 4 | Get memory summary | `GET /documents/{id}/memory-summary` (text + file prefix) |
| 5 | **Cognee: store document** (native) | Memory > Remember, unique prefix, background |
| 6 | Report memory result | `POST /documents/{id}/memory/result` |
| 7 | Mark graph building | After the loop, once |
| 8 | **Cognee: build knowledge graph** (native) | Cognify, waits for completion |
| 9 | Report graph result | `POST /cases/{id}/memory/graph-result` |
| 10 | Cross-check documents | `POST /cases/{id}/cross-check` |
| 11 | Issues found? | Branches to *Needs attention* or *Ready for KAM review* |
| side | **Cognee: find case dataset**, **list stored items**, Combine, Report | Records Cognee data ids so answers can cite sources; never blocks step 10 |

Every step that can fail continues instead of stopping the run.

### 9.2 Karyakarta - Voice chase (23 nodes)
* **Start** (`POST /webhook/karyakarta-voice-chase {case_id, to_number}`): get agent context, anything to chase?, **place call (Sarvam)**, call placed?, wait 15 s, check call, finished or timed out?, record result. A refused call goes to *Call not placed* with the reason.
* **Result** (`POST /webhook/karyakarta-voice-result {case_id, outcome, summary, transcript, call_id}`) for an already finished call, and the end of the Start flow: record call on case,
  worth remembering?, get memory summary, **Cognee: store call** (native), report, mark graph building,
  **Cognee: refresh knowledge graph** (native), report.

Both are generated by `n8n/build_workflow.py` and `n8n/build_voice_workflow.py`. If n8n is unreachable the backend runs the
document pipeline in-process. n8n 2.x publishes through an outbox: if a version is published while a node type is unknown it
is marked failed and not retried, so re-import and publish again (documented in `n8n/README.md`).

---

## 10. Audit trail and live updates

Every meaningful step writes an `AuditEvent` (actor, title, detail, tone, optional document). The table is append-only. It is
the **timeline** the KAM reads and the source of the **server-sent event stream**
(`GET /api/events` for all cases, `GET /api/cases/{id}/events` for one). The dashboard and case page refresh from it, so statuses
change live as documents are processed. SQLite runs in WAL mode so polling streams never block writes.

---

## 11. Security, privacy and compliance posture

| Area | What exists | What does not |
|---|---|---|
| Secrets | Only in `backend/.env` and the n8n credential; `.env` is git-ignored; keys are never logged or printed | No secrets manager |
| Input validation | Extension allow-list, 25 MB limit, empty-file rejection, SHA-256 per file | No antivirus scan |
| Network | CORS limited to the web app origin | No TLS in the local prototype |
| Decisions | Server-side role and stage guard; the agent and merchant are refused (403) for approve, submit, send back | Roles are labels in the request, not authenticated users, so maker-is-not-checker per person is not enforceable yet |
| Audit | Append-only trail of every AI and human action | No signed or externally anchored log |
| Data | All demo data synthetic; documents watermarked "SPECIMEN - SYNTHETIC DEMO DATA" | |
| **DPDP Act 2023** | Consent controls and the statutory consent text in the portal | **Consent is not recorded in the backend; no withdrawal flow; no data-retention policy** |
| RBI Payment Aggregator Directions | The workflow targets the document verification and re-verification burden | CKYCR lookup and ongoing monitoring are not built |

Document images and extracted text are sent to Sarvam and Cognee Cloud. A production deployment needs a data-processing
review for that, plus data residency and retention terms.

---

## 12. Reliability

| Mechanism | Behaviour |
|---|---|
| In-process fallback | If n8n is unreachable the backend runs the same steps |
| Graceful memory failure | A Cognee failure is recorded per document (`memory_status: failed`) and never blocks extraction, checks or the UI |
| Circuit breaker | 2 Cognee failures open the breaker for 20 s so a dead service cannot stall every request |
| Limiter and retries | Sarvam submissions paced and retried with backoff |
| Honest errors | Failures are written to the timeline with a readable reason |
| Reload safety | Uvicorn graceful shutdown limited to 2 s, reload watches `app/` only |
| Demo mode | Recorded Sarvam results and saved case answers keep the demo alive offline |

---

## 13. API reference (57 endpoints, all under `/api`, JSON envelope `{ok, data}`)

| Method and path | Purpose |
|---|---|
| `GET /health` | Status, demo mode, memory mode, n8n configured |
| `GET /cases` | KPIs and pipeline rows |
| `GET /cases/{id}` | Header, stages, checklist, checks, findings, summary, timeline, voice calls |
| `POST /cases/{id}/documents` | Batch upload (202) |
| `GET /cases/{id}/documents` | Document records with fields and boxes |
| `GET /documents/{id}`, `GET /documents/{id}/file` | One record; the original file (supports range requests for pdf.js) |
| `POST /documents/{id}/extract` | Sarvam extraction + per-document checks (called by n8n) |
| `POST /documents/{id}/locate` | Evidence boxes (digitise pass) |
| `POST /documents/{id}/status`, `POST /documents/{id}/type` | Status reported by n8n; KAM type correction |
| `GET /documents/{id}/memory-summary`, `POST /documents/{id}/memory`, `POST /documents/{id}/memory/result` | What to store in Cognee; store via backend; report-back from n8n |
| `POST /cases/{id}/memory/cognify`, `…/graph-start`, `…/graph-result`, `…/items`, `GET /cases/{id}/memory` | Graph build, status, source-id linking |
| `POST /cases/{id}/ask` | Ask this case (answer + sources; 503 if memory unavailable) |
| `POST /cases/{id}/cross-check` | Run the 10 checks and triage (returns `issues` for n8n) |
| `GET /cases/{id}/crm-form`, `POST /cases/{id}/crm-form/override` | CRM form; audited override |
| `POST /cases/{id}/action` (alias `/actions`) | voice, request, approve, submit_to_compliance, send_back, compliance_approve (role and stage guarded) |
| `GET /cases/{id}/voice-chase/context`, `POST /cases/{id}/voice-chase/result` | Agent variables and opening line; record a finished call |
| `POST /cases/{id}/voice-chase/call`, `GET /cases/{id}/voice-chase/attempts/{attempt_id}` | Place the outbound call through Sarvam; poll its status and transcript (called by n8n) |
| `GET /voice-calls/{id}/memory-summary`, `POST /voice-calls/{id}/memory/result` | Call text for Cognee; report-back |
| `GET /cases/{id}/timeline`, `GET /cases/{id}/events`, `GET /events` | Timeline; live event streams |
| `GET /mock-registry/{id}` | The mock MCA / GST / penny-drop record the checks compare against |
| `GET /cpv/{token}`, `POST /cpv/{token}/capture`, `POST /cpv/{token}/submit` | Drishti, public with the one-time token: capture state, one live-camera frame, send for verification |
| `GET /cases/{id}/cpv`, `POST …/cpv/link`, `POST …/cpv/analyse`, `GET …/cpv/images/{kind}`, `GET …/cpv/memory-summary`, `POST …/cpv/memory/result`, `POST …/cpv/demo-reference` | The case's verification, the link, running Drishti (n8n), evidence photos, Cognee storage, a labelled demo reference (off by default) |
| `GET /cases/{id}/vcip` | The V-CIP record. `POST …/action` adds `cpv_approve`, `cpv_retake`, `vcip_call`, `vcip_signoff`; `voice-chase/*` accept `kind=vcip` |
| `DELETE /documents/{id}?actor=kam`, `POST /cases/{id}/demo/reset` | KAM housekeeping: delete a submitted file (before Compliance; re-runs the checks, removes its Cognee items), and a demo-only reset of a seeded case (off unless `CPV_ALLOW_DEMO_REFERENCE=true`) |
| `GET /cases/{id}/settlements`, `POST …/settlements/scan`, `POST …/settlements/monitor`, `…/reconcile`, `…/investigate`, `GET /settlements/{id}/memory-summary`, `POST /settlements/{id}/memory/result`, `POST …/settlements/demo/spike`, `…/demo/reset` | Settlement Agent: the Settlements tab, starting the chain, the n8n steps, storing the finding in Cognee, demo controls (off by default). `POST …/action` adds `inv_resolve` and `inv_dismiss` (KAM only) |

Interactive documentation is generated at `http://localhost:8765/docs`.

---

## 14. Data model (SQLite)

| Table | Purpose and key fields |
|---|---|
| `Case` | id (KYB-…), slug, merchant and legal name, entity type, industry, CIN, PAN, GSTIN, registered and operating address, contact name and phone, stage 1 to 8, status, route, summary, graph status, SLA due |
| `Document` | case, type, filename, SHA-256, status, `fields` (value, confidence, page, boxes), per-document `checks`, `memory_status`, Cognee data ids |
| `CheckResult` | case, check id, label, status, detail, action, `evidence` (replaced on each cross-check) |
| `VoiceCall` | case, outcome, summary, transcript, Sarvam interaction id, memory status |
| `AuditEvent` | append-only: case, actor, title, detail, tone, document |
| `CrmOverride` | case, field, KAM value, AI value, actor, time |
| `CpvSession` | case, one-time token, status, expiry, captures (photo path, SHA-256, GPS, accuracy, bearing, times, EXIF flag), result (verdict, five checks, distance, signboard text), memory status |
| `VcipRecord` | case, status (queued, interviewed, signed_off), randomized questions with expected answers, transcript, call id, sign-off person and time |
(`Case` also gains `mcc` and the reference location fields; stage runs 1 to 10.)

---

## 15. Configuration (`backend/.env`)

| Variable | Meaning |
|---|---|
| `SARVAM_API_KEY` | Document Intelligence key (also used by the voice probe's speech-to-text and text-to-speech) |
| `SARVAM_CONNECTION_ID`, `SARVAM_AGENT_PHONE_NUMBER`, `SARVAM_AGENT_VERSION`, `SARVAM_CALLBACK_URL` | Outbound calling: the connected Twilio connection and number, the agent version (default 1), and an optional public webhook URL. Restart the backend after changing `.env` |
| `SARVAM_AGENT_ID`, `SARVAM_API_KEY_NEW_FOR_VOICE`, `SARVAM_ORG_ID`, `SARVAM_WORKSPACE_ID` | Voice agent. The runtime needs an **agent API key** (44 characters); the standard key is rejected with 401. The agent is call-only |
| `COGNEE_BASE_URL`, `COGNEE_TENANT_ID`, `COGNEE_USER_ID`, `COGNEE_API_KEY` | Cognee Cloud |
| `N8N_WEBHOOK_URL`, `N8N_VOICE_WEBHOOK_URL`, `N8N_FALLBACK_INPROCESS` | n8n entry points and fallback |
| `DEMO_MODE`, `PIPELINE_AUTORUN` | Serve recorded results; disable auto-run (tests and seeding) |
| `PORT`, `CORS_ORIGINS` | Backend port (8765) and allowed origins |

---

## 16. Testing and verification evidence

| Suite | Count | What it covers |
|---|---|---|
| Backend (pytest) | **172** | Extraction normalisation on **real Sarvam responses**, box location, validators, the 10 checks on the planted issues, CRM form, memory with a fake store, Cognee outage and circuit breaker, voice context and call records, role and stage guard, and an end-to-end test on the 8 real PDFs with recorded Sarvam responses |
| Frontend (Vitest) | **69** | Dashboard, case overview, evidence navigation, Ask, voice drawer and history, upload, offline fallback, rendered against **real backend responses** |
| Live, manual | n/a | Full upload through n8n with live Sarvam and Cognee; voice agent scenarios; Cognee 409 behaviour reproduced and fixed |

The tests never call Sarvam or Cognee. **Not verified in a real browser:** the layout, the pdf.js rendering and highlight boxes,
and live updates over SSE (the render tests cannot run pdf.js). Do a browser walkthrough before presenting.

---

## 17. Measured performance (development machine, 2026-10-02)

| Measure | Result |
|---|---|
| 8 documents, upload to routed case, through n8n, live Sarvam and Cognee | **about 108 s** (in-process fallback: about 150 s) |
| Sarvam extraction of 8 documents (paced by the 9/min limiter) | about 45 s |
| 10 cross-document checks | under 1 s |
| Storing one item in Cognee (Remember, background) | about 4 s |
| Graph build for a small case | 10 to 30 s |
| Seeded demo, documents from cache, no Sarvam calls | about 18 s |
| Fields located on the page (hero) | 47 of 51 |

No manual-baseline measurement exists. Do not quote hours saved unless you can source the baseline.

---

## 18. Known limitations and roadmap

**Limitations (be ready to say these):**
1. Registries are a **mock**. The checks are real; the "official record" they compare against is synthetic.
2. Voice: the agent works and calling is built, but **no real phone call has been placed yet**; chasing is KAM-triggered.
3. **No authentication.** Roles are asserted in the request; the guard is real but identities are not.
4. **DPDP consent is not recorded** by the backend; no withdrawal or retention flow.
5. WhatsApp and email are timeline entries, not messages.
6. Confidence is Sarvam's own score and is not accuracy: a misread was seen at 100%. The penny-drop comparison caught it.
7. Beneficial-owner look-through uses the **declared** partner table, not an independent registry.
8. Evidence boxes: 4 of 51 hero fields are not located; tables are boxed at table level.
9. Voice was tested in Hindi, Hinglish and English with a synthetic voice, not with real merchant speech or noise.
10. Built and tested for a handful of cases, not for load.
11. **Drishti on real phones:** the capture page has not been used on a real phone camera or GPS (it needs an https tunnel), nor on real storefront photographs.
12. **A web page cannot prove a photo is live.** The server checks and the evidence make spoofing hard and visible, not impossible.
13. **The screen-replay heuristic** was calibrated on synthetic images only and can miss a perfectly axis-aligned screen grid. The MCC check is a keyword match.
14. **Geocoding** uses OpenStreetMap, whose precision for real Indian street addresses was not tested; the demo needs a labelled reference point.
15. **V-CIP:** no face matching; the second voice agent needs to be created and was not tested; the human official's sign-off is the control, as RBI requires.

**Roadmap (each is one module or node):**
first real phone call and (optionally) Sarvam's call-completed callback · real MCA21 / GSTN / penny-drop adapters · CKYCR check · automatic chase
on the ASK route · authenticated users with person-level four-eyes and a DPDP consent ledger · WhatsApp/email dispatch ·
Day-100 monitoring (same merchant graph plus a transaction feed) · stages 8 to 10 integrations · real-phone testing of Drishti and a face-matching model for V-CIP.

---

## 19. Repository and running it

```
workflowkyc/
├── src/                      React app (merchant portal, KAM workspace, voice UI) + tests
├── backend/
│   ├── app/                  FastAPI: routes, extraction, checks, crm_form, memory, voice_agent, registry (mock)
│   ├── n8n/                  workflow generators + exported workflows + README
│   ├── voice/                Sarvam agent setup guide and verified scenarios
│   ├── scripts/              voice_agent_probe.py and Sarvam helpers
│   ├── seed/                 synthetic Sharma Foods PDFs + demo seeding
│   ├── demo_cache/           recorded Sarvam results and saved answers
│   └── tests/                172 tests
└── docs/                     these documents
```

Run order: `backend\run.bat` (port 8765) → n8n container (5678) with the three workflows published → `npm run dev` (5173).
Demo data: `seed.bat --reset`, or `seed.bat --reset --hero-docs` to preload the 8 documents. Full setup, environment variables,
the demo script and a troubleshooting table are in `backend/README.md`.
