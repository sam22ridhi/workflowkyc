# How to make the demo: preparation, screen flow and narration

For the presenter making a recorded (or live) demo of Karyakarta. Target length: **10 minutes**. The longer runbook (`07_DEMO_RUNBOOK.md`) has the fallbacks; the spoken evaluator script is `09_EVALUATOR_SCRIPT.md`. This file is the shortest path from "nothing running" to "finished demo".

## A. How to make it

### A1. One-time preparation (the day before)
1. **Top up the Sarvam credit** (document reading returned `402`), then run `seed.bat --record-fixes` so the corrected-cheque step also works offline.
2. **Repair the database**: stop the backend, rename `backend/karyakarta.db` to `karyakarta.db.bad`, start it again (it reseeds).
3. In `backend/.env`: `DEMO_MODE=true`, `CPV_ALLOW_DEMO_REFERENCE=true`, `CPV_MAX_ACCURACY_M=5000`. Restart the backend.
4. Print the four images in `backend/seed/shop/` on paper (never show them on a screen).
5. Commit `backend/demo_cache/` so the recorded Sarvam results travel with the repo.

### A2. Before every recording (10 minutes)
1. Start in this order: Docker (n8n) → `backend\run.bat` → `npm run dev` (http://localhost:5173). Wait about 25 seconds for the n8n webhooks.
2. `python scripts/demo_reset_all.py` (puts every demo case back to its start).
3. `python scripts/demo_preflight.py` (no ✘ allowed).
4. Open **three browser windows** side by side, all at 100% zoom, bookmarks bar hidden: **Merchant** (`/dashboard/upload`), **KAM** (`/kam`), **n8n** (`http://localhost:5678` executions). Close every other localhost:5173 tab.
5. Put the phone on silent. Have the 9 files from `backend/seed/demo_pack/` in one folder, and the 4 from `demo_pack/fixes/` in another.

### A3. Recording
* **Tool:** OBS Studio (free) at 1920×1080, 30 fps, screen capture of the browser window; or Windows `Win+Alt+R` (Game Bar). Record **per act** (9 short clips), not one long take, so a slip costs 1 minute, not 10.
* **Voice:** record the narration separately after the screen clips, reading the script below while watching the clip. It sounds better than talking and clicking at once.
* **Pace:** pause 2 seconds on each result before moving on. Zoom in (Ctrl +) on the finding or the timeline you are talking about.
* **Edit:** cut any waiting longer than 4 seconds (document reading, calls) with a "…" jump cut. Add a one-line title per act.
* **Disclose once, at the start:** "All documents and data are synthetic specimens."

## B. The flow of screens

| # | Screen (URL) | Who | What you do | What the viewer sees |
|---|---|---|---|---|
| 1 | Landing `/` | — | Show the page, click **Start onboarding** | The product front door |
| 2 | Merchant, Stage 1 `/dashboard/stage-1` | Merchant | Show "Account live, capped ₹50,000/month", click **Upload Stage-2 Documents** | The cap and the call to action |
| 3 | Merchant, Upload `/dashboard/upload` | Merchant | Drag in the 9 PDFs | Each file gets a SHA-256 and a detected type |
| 4 | KAM dashboard `/kam` | KAM | Show the pipeline (KPIs, case table), open **Sharma Foods** | Row moves to ESCALATE as documents are read |
| 5 | Case Detail, Overview `/kam/cases/KYB-20814` | KAM | Watch the Timeline fill; scroll the 10 checks | 6 pass, 4 fail, route ESCALATE |
| 6 | Evidence tab | KAM | Click a finding's evidence chip | The real PDF with the value boxed |
| 7 | MAF (Merchant Application Form) tab | KAM | Show the sources, confidence and conflict notes | 20 fields with citations |
| 8 | Ask this case | KAM | Ask "Who owns more than 10% of Sharma Foods?" | Cognee's answer with its source documents |
| 9 | Voice Chase drawer | KAM | Open it, show the Hindi opening line and "held back for KAM", press **Call now** (or play the rehearsal) | The call, then the transcript on the case |
| 10 | Trash icon, then Merchant Upload | KAM, Merchant | Delete the cheque; upload the 4 fix-pack files | Bank and owner findings clear; two remain |
| 11 | KAM: Approve & Forward | KAM | Confirm the ESCALATE dialog | Case goes to stage 5 |
| 12 | Switch to Compliance, Approve | Compliance | Press **Approve (Compliance)** | Stage 6: shop verification opens |
| 13 | Merchant, Action Required | Merchant | Show the **Verify your shop** card (link, QR) | A secure link in the communication centre |
| 14 | Capture page `/cpv/<token>` | Merchant | Take the 2 photos (or **upload a picture** with the demo option), send | Verifying… |
| 15 | KAM: Drishti card | KAM | Show the signboard read, distance, five checks | **CPV_VERIFIED**, case to V-CIP |
| 16 | Compliance: V-CIP card | Compliance | Show the questions and transcript, click **Sign off** | Case moves on |
| 17 | KAM: Annapurna Sweets, Settlements tab | KAM | **Inject 48-hour spike**, then **Run settlement check** | The 5-step chain in the Timeline |
| 18 | KAM queue: INV- case | KAM | Open it: exception cards, twin context, payments, brief; **Resolve** | The investigation, closed by a person |
| 19 | Architecture page | — | Show the seven teammates | The close |

## C. The narration (read as the voice-over)

**Opening (screens 1–2, 30 s).**
"A company that goes live on Paytm's gateway starts with just a PAN and a bank account, capped at fifty thousand rupees a month. Lifting that cap means checking a full set of documents by hand. This is Karyakarta: a team of AI teammates that does the document work, so a person only has to decide. Everything you'll see uses synthetic specimen documents."

**Upload (screen 3, 30 s).**
"The merchant, Sharma Foods Private Limited, just drops in their documents. Each file gets a fingerprint, and Karyakarta recognises what each one is. From here, no human touches anything until a decision is needed."

**The AI team at work (screens 4–5, 60 s).**
"Behind the scenes an n8n workflow conducts the team. Sarvam Document Intelligence reads every document using a schema for that document type, and returns each value with a confidence and the page it came from. Plain Python rules then check the documents against each other and against the registry. And each merchant's information is stored in its own Cognee knowledge graph. In about a minute and a half we have a result: six checks pass, four fail, and the case is routed **ESCALATE**, meaning a person has to judge."

**The four conflicts (screens 5–6, 90 s).**
"Four problems, planted the way a real KAM finds them. One: the board resolution authorises Ravish Sahay, who is not on the director list. We don't reject it, because a board can delegate authority: we escalate it to a human. Two: the shareholding shows an LLP holding thirty percent. We look through it: Rakesh Sharma owns sixty percent of that, which is eighteen percent of the company, above the ten percent rule, with no identity proof on file. Three: the cheque says 'Sharma Foods' but the legal name is 'Sharma Foods Private Limited', and for the settlement account the match must be exact; the merchant can fix this. Four: GST, FSSAI and the electricity bill say Navi Mumbai while the application says Mumbai. Every finding links to the exact page, and when I click it the PDF opens with the value boxed. The rules depend on the entity type: a private or public company needs a board resolution and a shareholding declaration, a proprietorship does not."

**CRM form and Ask (screens 7–8, 45 s).**
"The same data fills the CRM form, twenty fields, each with its source and a note where two documents disagree. And I can ask the merchant's graph a question: who owns more than ten percent? Cognee answers and names the documents. It explains. It never decides pass or fail."

**Voice call (screen 9, 60 s).**
"Instead of chasing the merchant for an afternoon, the KAM presses Voice Chase. This drawer shows exactly what the agent will say in Hindi. Only things the merchant can fix are sent: the cheque, the address, the missing KYC. The signatory and the hidden owner are held back for the KAM. The agent refuses OTPs and promises nothing about approval. When the call ends, the transcript lands on the case and in the merchant's memory."

**Fixing it (screens 10–11, 60 s).**
"The merchant uploads a corrected cheque and the identity proofs of the other owners. The KAM can delete the wrong file, the checks re-run, and the findings the merchant could fix clear. Two remain, because they need judgement. The KAM approves and forwards, and the system asks for confirmation because the case is still flagged."

**Four eyes, shop and video KYC (screens 12–16, 120 s).**
"A second person, Compliance, approves. The server enforces it: the agent and the merchant are refused. Now Drishti. The merchant gets a secure, camera-only link in their communication centre, no WhatsApp. They take two live photos with GPS. Drishti reads the signboard, in Hindi here, matches it to the GST trade name, measures the distance to the declared address and checks the capture is live. All checks pass, so it issues **CPV_VERIFIED** on its own. If anything were doubtful it would never fail the shop: it would go to a person. Then video KYC. RBI needs a human official, so we prepare it: a Hindi pre-interview with randomised questions, and the official signs off in one click. We do not match faces."

**After go-live (screens 17–18, 90 s).**
"Onboarding is where fraud enters; settlement is where money leaves. Annapurna Sweets has thirty days of normal settlement. I'll inject a forty-eight-hour spike. Two fixed thresholds start the Settlement Agent: volume above a hundred and fifty percent of baseline, or settlement more than ten percent off. Watch the timeline: monitor, reconcile, investigate, create case, escalate. It pulls the merchant's declared profile from Cognee, finds the exact payments, from a new terminal in another city at night, has Sarvam write a brief with every number checked, and opens a case in the same queue. It recommends. A person resolves it."

**Close (screen 19, 30 s).**
"Seven teammates: n8n conducts, Sarvam reads and speaks, rules decide, Cognee remembers, a voice agent chases, Drishti verifies the shop, and a settlement agent keeps watching. The model reads, code checks, the model explains, a human approves. What isn't built yet: the registries are a labelled mock, there is no login or stored consent, and the shop and settlement features were tested on synthetic data. Thank you."

## D. If something goes wrong while recording

| Problem | Fix |
|---|---|
| Documents stay "extracting" | `DEMO_MODE=true` and restart the backend; `scripts/demo_reset_all.py`; upload again |
| Page spins on upload | Close other `localhost:5173` tabs and reload |
| Call does not connect | Show the reason on the timeline, then play the rehearsal: `python scripts/voice_agent_probe.py KYB-20814 --record` |
| Camera blocked | Use **Demo only: upload a picture instead** (`storefront_hindi_sign.jpg`, then `counter_menu_and_qr.jpg`) after setting the reference point on the KAM's Drishti card |
| Anything stuck | `python scripts/demo_reset_all.py`, reload, re-record that clip |
