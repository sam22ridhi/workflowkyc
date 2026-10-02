# Karyakarta: Hackathon Q&A

*Team Genesis51 · Paytm Build for India AI Hackathon, Mumbai · Track 3: Autonomous AI Teammates*

How to use this: answers are short on purpose, written for you to say out loud. Each states what is true **today**.
Where something is mocked, not built, or unmeasured, the answer says so. Judges reward a clear "not yet, here is the seam"
far more than a bluff, and the status matrix in the technical documentation backs every line.

**Before you present, verify:** the RBI wording and dates against the Directions text (your brief says the Payment
Aggregator Directions are dated 15 Sep 2025 with existing merchants due by 15 Sep 2026; that date has already passed, so say
"the deadline was 15 September 2026" or "the industry is working through re-verification", not "is coming"), and fill in who
built what in section J.

Contents: A Problem · B Product · C Track 3 and agents · D Technology choices · E Accuracy, safety, trust · F Voice ·
G The demo · H Business and scale · I Hard questions · J Team · K Numbers to remember

---

## A. The problem

**A1. What problem are you solving?**
Onboarding non-individual merchants (companies, LLPs, partnerships, trusts) to Paytm's gateway is slow and manual. A business
goes live instantly with PAN and a bank account but is capped at ₹50,000 a month. Lifting the cap needs a full document set,
and someone has to check names across documents, that the signatory is a current director, every beneficial owner above 10%
through other companies, the bank account against the legal name, and addresses. The KAM does it by hand over email, WhatsApp
and calls, and a mismatch found late means another round trip while the merchant stays capped.

**A2. Why is this hard to automate? Banks and PSPs already use OCR.**
OCR plus rules handles the simple cases. Company cases with layered ownership and signatory questions always fall to manual
review, and that is the slowest part. That is the hard 20% we target.

**A3. Who is the user?**
The Key Account Manager (maker) and the Compliance officer (checker) inside Paytm, with the merchant's signatory as the other
party. The KAM is the person whose time we give back.

**A4. Why now?**
Per our brief, the RBI Payment Aggregator Directions (15 Sep 2025) require full KYC, use of the central KYC registry (CKYCR) and
ongoing monitoring of every merchant, with existing merchants due by 15 Sep 2026, so the whole industry is re-verifying merchants at
once. (Check the exact wording against the Directions before quoting it; the date has passed.)

**A5. What does the delay cost?**
The merchant stays at the ₹50,000 cap, so it loses revenue, and Paytm loses the processing revenue on the volume that cannot flow.
We have **not** measured a baseline of KAM hours or days, so we do not quote one.

**A6. Who feels the pain most?**
The merchant with layered ownership: a company that holds shares through an LLP or another company. Those cases need an owner
chain traced and a signatory authority confirmed, which is exactly what simple automation skips.

---

## B. The product

**B1. In one sentence, what is Karyakarta?**
An AI teammate for the KAM that does the document work of corporate onboarding (read, check, trace ownership, remember, chase the
merchant in Hindi) so the KAM only makes decisions.

**B2. What does "Karyakarta" mean?**
कार्यकर्ता, "the one who does the work".

**B3. Walk me through the flow.**
The merchant uploads documents after giving consent. Sarvam reads each one into fields with a confidence and a page location. Plain
Python rules run 10 cross-document checks. Cognee builds a knowledge graph of the merchant, the "Merchant Digital Twin". The case is
routed AUTO, ASK or ESCALATE. n8n runs all of it. The KAM reviews as maker, Compliance approves as checker.

**B4. What are AUTO, ASK and ESCALATE?**
AUTO: everything checks out, the KAM approves with one click. ASK: something the merchant can fix, so the agent explains it in Hindi
and asks for the right document. ESCALATE: needs human judgement (for example the signatory is not a current director, or a hidden
beneficial owner), with all the evidence attached.

**B5. What does the KAM actually do now?**
Decides. They open a case that is already read, checked and explained, look at the findings with evidence, overrule or confirm, chase
if needed, and approve and forward.

**B6. What is the Merchant Digital Twin?**
A Cognee knowledge graph of one merchant built from all its documents and calls: people, companies, ownership, addresses, accounts,
conversations. The KAM can ask it "who owns more than 10%?" and see the hidden owner with the source document.

**B7. What about Day 100, after go-live?**
That is the roadmap: use the same merchant record to watch transactions against the business profile, as the RBI now expects. It is
**not built**. The graph and audit trail it would sit on are.

**B8. What are the 10 checks?**
Legal name consistency; PAN valid and matches entity type; GSTIN contains the PAN; CIN valid and matches; signatory is a current
director; beneficial owners above 10% identified and KYC'd; bank holder matches the legal name and the penny-drop; addresses
consistent; required documents present; industry licence present and valid (only food/FSSAI is configured today).

**B9. Which documents does it read?**
Eight types: company PAN, GST certificate, certificate of incorporation, board resolution, cancelled cheque, director KYC,
shareholding declaration and FSSAI licence.

**B10. How does it find a hidden owner?**
The shareholding declaration lists shareholders and, for company or LLP shareholders, their partners. The Verifier computes effective
ownership: Sharma Holdings LLP holds 30%, Rakesh Sharma has 60% of it, so he owns 18% effectively. Above 10% and no KYC on file means
ESCALATE.

---

## C. Track 3 and the agents

**C1. Why is this an "autonomous AI teammate" and not a chatbot?**
Because nobody asks it anything. When eight documents are uploaded it reads them, runs the checks, finds the problems, fills a 20-field
CRM form, builds the graph, drafts the merchant call and routes the case, all unprompted. "Ask this case" is one feature of ten.

**C2. Who are the AI teammates?**
Five: the Orchestrator (n8n), the Reader (Sarvam Document Intelligence), the Verifier (deterministic rules), the Digital Twin analyst
(Cognee) and the Voice Chaser (Sarvam voice agent). Two humans decide: the KAM and Compliance.

**C3. How autonomous is it really?**
Reading, checking, routing, memory and drafting are fully autonomous. The voice chase runs on its own once triggered; today the KAM
clicks the button, and an automatic trigger for ASK cases is a one-branch change in n8n. Decisions are human-only by design.

**C4. What can the agent never do?**
Approve, reject, send back or overrule a finding. The API refuses (HTTP 403) if the actor is the agent or the merchant, and Compliance
can act only after the KAM has submitted. On calls it never promises approval, never takes OTPs or account numbers, and never raises
issues reserved for the KAM.

**C5. Why not one big LLM agent that does everything?**
Because pass/fail on KYC must be repeatable and explainable. An LLM can misread a document or be talked into a different answer; a
rule cannot. So the model reads and explains, code checks, and a human approves.

**C6. Where is the human in the loop?**
At every decision: the KAM approves and forwards, Compliance gives the second approval. Findings are suggestions with evidence; the
human can overrule any of them, and overrides are audited.

**C7. How do you show autonomy and control together?**
The autonomy ladder: reading, checking, routing and memory are autonomous (A3); the voice chase is KAM-triggered (A2); approvals are
human-only (A0); and we deliberately use no level where the AI decides (A4).

---

## D. Technology choices

**D1. Why n8n?**
It is the orchestrator and it is visible: ops can open the workflow and see each step. It runs extraction, memory, cross-checks and
the voice chase as two workflows (37 nodes) with native Cognee nodes, and every step can fail without stopping the batch. It is one of the
hackathon's partner tools and it earns its place: remove it and the backend falls back to an in-process pipeline, but you lose the
visible, editable workflow.

**D2. Why Cognee?**
Layered ownership is a graph problem and the KAM needs to ask questions across documents. Cognee gives a per-merchant knowledge graph
with search and answers, through native n8n nodes. It also becomes the base for Day-100 monitoring.

**D3. Why Sarvam?**
Indian documents and Hindi voice. Document Intelligence reads our eight document types into a schema with confidence and page numbers; the
Samvaad agent speaks to the merchant in Hindi. It is the natural fit for India-specific onboarding.

**D4. Which model answers "Ask this case"?**
Cognee's. The backend calls Cognee's graph-completion search and Cognee's model writes the answer. Sarvam reads documents and speaks;
it does not answer case questions.

**D5. What does Sarvam do exactly, and which calls?**
Per document: one extraction (values, confidence, page) and one digitise (layout boxes so values can be highlighted on the page). So 16 jobs
for an 8-document case, paced by a limiter. Plus the voice agent for calls.

**D6. Why plain Python for the checks?**
Determinism and evidence. PAN type, GSTIN-contains-PAN, effective ownership and name matching are exact logic. No LLM decides pass or fail,
so results are repeatable and auditable.

**D7. Why FastAPI and SQLite?**
FastAPI for typed, documented endpoints (33) and server-sent events; SQLite (WAL mode) as the single system of record so Cognee can fail
without losing a case. It is a prototype choice: production would use Postgres.

**D8. What if Cognee is down?**
Extraction, checks, the CRM form and the UI keep working. Documents show "memory failed", Ask returns a clear message (or a saved answer in
demo mode), and a circuit breaker stops a dead service from slowing every request.

**D9. What if n8n is down?**
The backend runs the same pipeline in-process and says so on the timeline. An upload never stalls.

**D10. How did you find the Cognee limitation you mention?**
Cognee Cloud refuses a second upload that re-uses a file name with different content (HTTP 409), and the plain Add node always uses the same
name. We reproduced it directly and moved both workflows to the Remember operation with a unique file prefix per document and call.

**D11. How do answers cite sources if Cognee returns no ids?**
After the graph build, n8n lists the dataset's items and reports their ids and names to the backend, which maps them back to documents. So an
answer can name its source document.

**D12. Do you handle documents in Hindi or other languages?**
Sarvam supports Indian languages, but we tested document reading only on **English, synthetic** documents. Regional-language documents are
untested.

---

## E. Accuracy, safety and trust

**E1. What about hallucination?**
The model never decides. Extracted values carry confidence, page and a box so a human can verify them; checks are code; the voice agent is
limited by a prompt and by what we send it (only merchant-fixable items).

**E2. How accurate is the extraction?**
We have not measured accuracy over a labelled set, so we give no percentage. On the 8-document hero case Sarvam returned 51 fields with
confidence 99.5 to 100%, and 47 were located on the page.

**E3. Confidence is high, so it is right?**
No, and we saw it. Sarvam read a cheque account number as `500034928174` instead of `50200034928174` at 100% confidence because a "CANCELLED"
stamp covered digits. The check against the bank's penny-drop record catches this class of error. That is why confidence is shown, not trusted.

**E4. What if the AI misses a beneficial owner?**
The look-through uses the declared partner table, so a hidden owner who is not declared would not be found by the table alone. The check also
compares the declaration with the registry record and escalates a mismatch. In production a real registry and CKYCR lookup would close more of this.
A human still decides every case.

**E5. How do you stop the agent from approving?**
The API enforces it: approve, submit, send back and compliance-approve return 403 unless the actor is the right human role, and compliance can act only
after the KAM has submitted. There is a test for each combination. (Roles are labels today, not authenticated accounts.)

**E6. Is it auditable?**
Every AI and human action is an event in an append-only trail: the timeline the KAM reads, and the source of the live updates. Overrides keep the
AI's original value. It is not externally signed or anchored.

**E7. Can a KAM overrule it?**
Yes, anywhere. Findings are evidence-backed suggestions; CRM fields can be edited (audited); the KAM can approve an ESCALATE case after confirming.

**E8. What about DPDP?**
The portal shows consent controls and the statutory consent text. **The backend does not yet record consent**, withdrawal or retention. That is on
the roadmap as a consent ledger.

**E9. Where does the data go?**
Documents and extracted text go to Sarvam and Cognee Cloud. Demo data is synthetic. A production deployment needs a data-processing review,
residency and retention terms with both vendors.

**E10. Can it detect forged documents?**
No. It checks consistency across documents and against a registry record; it does not do image forensics. Forgery detection is not in scope for the prototype.

**E11. Is the AI biased?**
It does not score people. It checks fields and relationships by rule, so the same inputs always give the same result. The voice agent speaks in the
merchant's language and is limited to a script of fixable items.

---

## F. The voice agent

**F1. What is the voice agent built on?**
A Sarvam Samvaad agent. It is configured in the Sarvam console and driven by variables from the live case: contact name, business name, the issues in
Hindi and English, the documents to send and where to upload.

**F2. Has it called a real merchant?**
No. We verified the agent live against a **scripted merchant** (voiced with Sarvam text-to-speech) in seven scenarios. Placing real phone calls needs
telephony, which is not set up yet. In n8n that is one placeholder node.

**F3. What did you test?**
Opening with the right name and item count; agreeing; busy (asks a callback time); asking for English (switches); "when will I be approved?" (no promise,
defers to the account manager); offering an OTP (refuses, documents only via the app); wrong number (apologises, ends); asking about the signatory
issue (does not discuss it).

**F4. How do you keep it from saying the wrong thing?**
Two layers. What we send it: only merchant-fixable items; issues for the KAM are never in its variables. What it is told: no promises, no OTPs or account
numbers, one topic, hand everything else to the account manager.

**F5. Is the call recorded and stored?**
The outcome, summary and transcript become a call record on the case and go into the merchant's Cognee memory, so the KAM can ask "what did the merchant say?".

**F6. What about WhatsApp and email?**
They appear in the drawer and on the timeline, but nothing is sent. Voice is the channel we built.

**F7. Does it work with regional accents, noise, code-mixing?**
Not tested beyond clean synthetic speech in Hindi, Hinglish and English.

**F8. Why voice at all?**
A rejection email is cold and uninformative and causes the round trip. A short call in the merchant's own language that names the exact document to send
removes the ambiguity.

---

## G. The demo

**G1. Is the data real?**
No. Sharma Foods is synthetic and every page is watermarked "SPECIMEN - SYNTHETIC DEMO DATA".

**G2. Are MCA21, GSTN and the bank real?**
No. They are a clearly labelled mock (`mock_registry.py`). The checks are real; the "official record" they compare against is synthetic.

**G3. What are the four planted problems?**
The cheque holder name does not match the legal name; the board-resolution signatory is not a current director; a hidden 18% owner sits behind Sharma
Holdings LLP; the GST address says Navi Mumbai while the application says Mumbai.

**G4. How long does it take?**
About two minutes for eight documents end to end through n8n with live Sarvam and Cognee (108 seconds measured). Checks take under a second.

**G5. What if the network fails during the demo?**
`DEMO_MODE=true` serves the recorded Sarvam results and saved answers; `seed.bat --reset --hero-docs` preloads the case in about 20 seconds. Memory shows as
unavailable but everything else works.

**G6. What is genuinely live in the demo?**
Upload, extraction by Sarvam, the 10 checks, routing, the CRM form, the evidence viewer, Cognee memory and Ask, the n8n workflows and the voice-chase
context. Not live: the registries (mock) and the phone call.

---

## H. Business and scale

**H1. What is the impact?**
Fewer round trips and less KAM time on the slowest cases, so merchants leave the ₹50,000 cap sooner. We have no measured baseline, so we frame it as a
pilot to measure: time to decision and number of merchant round trips, before and after.

**H2. What does it cost per case?**
We have not costed it. Per 8-document case it makes 16 Sarvam jobs, 8 Cognee stores and one graph build, plus one voice call if chased; pricing depends on
the vendor plans.

**H3. How does it scale?**
Today the ceiling is Sarvam's rate limit on our key: 10 job submissions a minute, so roughly one case every two minutes on one key. Production needs a
higher-limit plan, queueing in n8n, Postgres instead of SQLite and several workers. The design (stateless backend, n8n workflow per batch) allows that.

**H4. How would it plug into Paytm?**
The backend is the system of record with a REST API; the CRM form maps to the master application. The registry adapters, telephony, authentication and the
CRM push are the integration seams.

**H5. What is the moat?**
The decision architecture (deterministic checks plus evidence plus human approval), the ownership look-through, and the merchant graph that doubles as the
base for ongoing monitoring.

**H6. What next after the hackathon?**
Telephony and the call-completed callback; real MCA21 / GSTN / penny-drop adapters; CKYCR; auto-chase on ASK; authenticated users with person-level four-eyes
and a DPDP consent ledger; Day-100 monitoring.

---

## I. Hard questions

**I1. Isn't this just OCR plus GPT?**
No, on three counts. Pass/fail is deterministic code, not a model. The value is in the cross-document logic (look-through ownership, signatory authority) that
OCR does not do. And the AI is separated from the decision by design and enforced by the server.

**I2. What did you build in the time, and what is mocked?**
Built and tested: upload, extraction, 10 checks, routing, CRM form, evidence viewer, Cognee memory and Ask, two n8n workflows, the voice agent and call
history, the maker/checker guard. Mocked: registries. Not built: telephony, DPDP consent record, authentication, CKYCR, monitoring.

**I3. Who is liable if the AI misses something?**
The decision is human: the KAM and Compliance approve. The AI produces evidence and routes; it cannot approve. Liability and process stay with Paytm's maker-checker.

**I4. What would break first at 10,000 cases a day?**
Sarvam's per-key rate limit, SQLite, and a single backend process. Each has a known replacement (higher-limit plan and queueing, Postgres, workers behind a
load balancer); none was built.

**I5. What is the false-negative risk?**
A real one. Rules only check what is in the documents and the registry record; a forged document or an undeclared owner can pass. That is why ESCALATE exists, why a human
approves, and why real registries and CKYCR are on the roadmap.

**I6. Why should a KAM trust it?**
Because every finding opens the source: the document, the page, the box. They can verify in seconds, overrule, and see their own override recorded next to the AI's value.

**I7. Is Cognee a lock-in?**
It is behind a small interface (a memory store with add, cognify, search); SQLite holds the truth. The graph can be rebuilt from the stored documents.

**I8. What did not work the first time?**
Several honest ones: Sarvam's extraction returns no coordinates (so we added a second layout pass and box matching); a cheque account number was misread at 100% confidence
(the penny-drop check catches it); Cognee Cloud rejected re-used file names (409), which we fixed with unique prefixes; and the voice agent needed a different API key type and
is call-only (so we test it by playing the merchant's voice into a call).

**I9. Why only these eight documents?**
They cover the brief's set for companies, LLPs, partnerships and proprietorships. The schema-per-document design makes adding a type a configuration task.

**I10. Can it handle partnerships and trusts?**
Entity rules exist for private and public limited, LLP, partnership and proprietorship (required documents and PAN type). Trusts are in the PAN-type mapping but have no required-document set yet.

---

## J. The team

**J1. Who is on the team and who built what?**
Team Genesis51: Ritika Iyer and Samridhi Raj Sinha. *[Fill in the split: for example product and frontend, backend and AI pipeline.]*

**J2. What did you learn?**
Separating reading from deciding made the system both safer and easier to build: each AI part could fail or be replaced without touching the decision logic.

---

## K. Numbers to remember

| Fact | Value |
|---|---|
| Planted problems found on Sharma Foods | 4 of 4, each with evidence |
| Documents / fields read | 8 documents, 51 fields |
| Fields located on the page | 47 of 51 |
| CRM form | 20 of 20 fields filled, 2 conflicts |
| Cross-document checks | 10 (6 pass, 4 fail on the hero case) |
| Hidden owner | Rakesh Sharma 18% (60% of Sharma Holdings LLP's 30%) |
| Upload to routed case | about 108 s through n8n (8 documents) |
| Check runtime | under 1 s |
| AI teammates | 5 (+ 2 human roles) |
| n8n | 2 workflows, 37 nodes, native Cognee nodes |
| Endpoints | 33 |
| Tests | 64 backend, 21 frontend |
| Voice scenarios verified | 7 (live agent, scripted merchant) plus the opening line |
| Not built | telephony, DPDP consent record, authentication, CKYCR, Day-100 monitoring |
