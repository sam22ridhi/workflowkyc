# Demo runbook: the whole Karyakarta story in about 12 minutes

Audience: the two presenters (Ritika, Samridhi). Everything here is synthetic. Where a step depends on something I could not verify, it says so.

## 0. The one-line story

*Karyakarta is a team of seven AI teammates that takes a company from "capped at ₹50,000" to live, and keeps watching after: the model reads, code checks, the model explains, a human approves.*

## 1. The day before

| Do | Why |
|---|---|
| **Top up the Sarvam credit.** The preflight found `402 Insufficient credit balance` | Without credit only documents with a recorded result can be read |
| `seed.bat --record-fixes` once the credit is back | Records the four fix-pack documents so the live "merchant fixes it" moment also works offline |
| **Commit `backend/demo_cache/`** (the recorded Sarvam results are new untracked files) | A fresh clone otherwise has no recorded results; `tests/test_demo_pack.py` checks them |
| Stop the backend, rename `backend/karyakarta.db` to `karyakarta.db.bad`, start it again | The DB was damaged by git deleting the tracked `-wal`/`-shm` files. `git rm --cached backend/karyakarta.db-*` and add `*.db*` to `.gitignore` |
| `.env`: `CPV_ALLOW_DEMO_REFERENCE=true`, `CPV_MAX_ACCURACY_M=5000`, `DEMO_MODE=true` | Demo upload, reference point, resets, the spike; recorded Sarvam results served first |
| Print `backend/seed/shop/*.jpg` on paper | The screen-replay check flags a photo of a screen. Never show them on a screen |
| For a phone camera: an https tunnel, `PUBLIC_APP_URL=<tunnel>`, frontend with `VITE_API_URL=` empty | Browsers allow camera and location only on https. Laptop webcam works without it |
| Verify the destination number in Twilio and enable India calling | A trial account can call only verified numbers |
| Rehearse the whole script twice, with a timer | |

## 2. Ten minutes before

1. Start, in this order: Docker (n8n) → `backend\run.bat` → `npm run dev`. Wait about 25 seconds for the n8n webhooks.
2. `python scripts/demo_reset_all.py` puts every demo case back to its starting state (it also clears Sharma's Cognee memory).
3. `python scripts/demo_preflight.py` must show no ✘. Warnings are things to know.
4. Open three browser windows: **Merchant** (`/dashboard/upload`), **KAM** (`/kam`), and the **n8n** executions list. Keep the architecture page ready.

## 3. The demo

Documents: `backend/seed/demo_pack/` (nine documents, drag them all in at once) and `backend/seed/demo_pack/fixes/` (four, for Act 5).
They look like the paperwork a KAM receives; each carries a "SPECIMEN - SYNTHETIC DEMO DATA" watermark. Say so before anyone asks.

**Happy-path alternative:** `backend/seed/demo_pack_correct/` (twelve documents) has no planted problem. Upload it, then in the KAM's **MAF (Merchant Application Form)** edit *Operating / Principal Address* to the Navi Mumbai address (note: confirmed with the merchant). The checks re-run and the case becomes **AUTO** with one-click approval. Use it as the contrast to the Sharma story, or when an evaluator asks "what does a clean case look like?". Five of its twelve files (04, 05, 07, 08, 09) have no recorded Sarvam result yet, so they need Sarvam credit.

### Act 1 · The merchant uploads (1 min)
*Merchant window, "Testing as" = Sharma Foods.* Open **Upload documents** and drop the nine PDFs. **Show:** each file gets a SHA-256 and a detected type; the page does not wait for the reading.
**Say:** "The merchant just uploads. Everything after this is the AI team."

### Act 2 · The team works, live (1 min)
*KAM window, Sharma Foods case, Timeline.* Watch events arrive: stored, read, stored in Cognee memory, cross-check complete. *n8n window:* the document workflow running. **Say:** "n8n conducts; Sarvam reads; Cognee remembers; plain Python checks."
**Takes** about 100 seconds through n8n with live Sarvam; with `DEMO_MODE=true` and recorded results, about a minute.

### Act 3 · The KAM decides what is left (3 min)
Route **ESCALATE**, four findings. Walk them:
1. *Board signatory (Ravish Sahay) is not a current director* (the registry lists Anil and Priya): needs human judgement.
2. *A hidden 18% owner* behind Sharma Holdings LLP (Rakesh 18%, Meera 12%, and Priya has no KYC): the look-through. Click the evidence chip: the PDF opens with the value boxed.
3. *Cheque says "Sharma Foods", not "Sharma Foods Private Limited"*: the merchant can fix.
4. *GST says Navi Mumbai, the application says Mumbai*, and the electricity bill agrees with GST.
Then open **MAF (Merchant Application Form)** (20 fields, each with its source citation, and the conflicts it found) and **Ask this case**: "Who owns more than 10% of Sharma Foods?" (answer cites the shareholding declaration).
**Say:** "The model never decides pass or fail. Every result has its evidence."

### Act 4 · Voice Chase (1.5 min)
**Voice Chase** → the drawer shows the exact Hindi opening line and what is held back for the KAM (the signatory and owner issues never reach the agent). Press **Call now** on a real phone (+91…), or play the rehearsal (`python scripts/voice_agent_probe.py KYB-20814 --record`).
**Say:** "It only chases what the merchant can fix. It refuses OTPs and promises nothing." *Fallback:* if the call fails, the case timeline shows Twilio's reason; use the probe.

### Act 5 · The merchant fixes it, the KAM keeps control (1.5 min)
*KAM window:* press the **trash icon** next to *Cancelled Cheque*: the file is deleted, the checks re-run (the cheque is now missing), and its copy leaves the merchant memory.
*Merchant window:* upload the fix pack: the corrected cheque (full legal name) and the KYC of Priya, Rakesh and Meera. The bank finding and the owner KYC clear; the board signatory and the address remain, because those need a person.
**Say:** "Karyakarta gets the merchant to fix what they can; it leaves the judgement calls to the KAM." Then **Approve & Forward** (confirm the ESCALATE dialog).
*Needs Sarvam credit or recorded fixes (see section 1). The check logic for these fixes is covered by tests, but the four fix-pack files themselves have **not yet been read live** (the Sarvam credit ran out before I could), so rehearse this act once after topping up.*

### Act 6 · Compliance, then Drishti (2 min)
Switch to **Compliance (Checker)**: *Approve*. The case moves to stage 6 and the merchant's **AI Communication Center** shows *Verify your shop* with a link and QR (no WhatsApp).
Open the link. On a laptop: **Demo only: upload a picture instead** with `storefront_hindi_sign.jpg` then `counter_menu_and_qr.jpg` (first set the reference point on the KAM's Drishti card: *Use this device's location*, *Save*). On a phone with the tunnel: take the printed photos live. **Send for verification.**
**Show:** the signboard read in Hindi and matched to the English GST trade name, the distance, the five checks, **CPV_VERIFIED**, the case moves to V-CIP.
**Say:** "It replaces a field visit. It never fails a shop on its own: a doubt goes to a person." For contrast, a wrong sign (the English-sign image on another case) gives NEEDS_REVIEW.

### Act 7 · V-CIP sign-off (1 min)
*Compliance, V-CIP card:* randomized Hindi questions, the pre-interview call (second Sarvam agent), the transcript, selfie and ID side by side, one-click **Sign off**.
**Say:** "RBI needs a human official. We cut the work to thirty seconds. We do not match faces."

### Act 8 · After go-live: the Settlement Agent (2 min)
Merchant **Annapurna Sweets & Snacks** (KYB-20820): *Settlements* tab: healthy, about ₹40K a day. **Inject 48-hour spike (demo)** → **Run settlement check**.
Watch the Timeline: MONITOR, RECONCILE, INVESTIGATE, CREATE CASE, ESCALATE (about 15 to 40 seconds). A new **INV-** case appears in the KAM queue marked *Settlement investigation*. Open it: four exception cards, what the Cognee merchant twin holds (a single outlet in Pune), the attached payments, the recommended action, the Sarvam brief.
**Say:** "Only two fixed thresholds start it. It recommends; it never moves money." Press **Resolve**, then **Reset**.

### Act 9 · Close (30 s)
The architecture page: seven teammates, four n8n workflows. Then the honest list (section 5).

## 4. When something goes wrong

| Symptom | Do |
|---|---|
| Upload page spins, then "took too long" | Close old tabs on `localhost:5173` (each held live-update connections); reload |
| Documents stay "extracting" | Sarvam credit or network: set `DEMO_MODE=true`, restart the backend, reset, upload again |
| n8n webhook "not registered" | Publish the workflow, `docker restart n8n`, wait about 20 s |
| Voice call "not placed" | Read the reason on the timeline (Twilio verified number / geo permission / credit); use the probe |
| Camera blocked | Use *Demo only: upload a picture instead* |
| "Distance … from the declared address" fails | Set the demo reference point first (KAM's Drishti card) |
| Backend will not start: "database disk image is malformed" | Rename `karyakarta.db` and start again |
| Anything stuck | `python scripts/demo_reset_all.py`, then reload the pages |

## 5. What not to claim

Registries are a labelled mock. DPDP consent is not recorded and there is no authentication. WhatsApp and email are timeline entries, not sent. Drishti has not been used on a real phone or a real shopfront, the screen-replay check is a heuristic, and there is no face matching.
The Settlement Agent runs on a synthetic ledger with fixed thresholds and has no scheduler. Savings of ₹250 to ₹500 and 3 to 5 days per field visit are the brief's figures, not ours. A real outbound call is the one piece to rehearse on the day.

## 6. Timing sheet

| Act | Min | Act | Min |
|---|---|---|---|
| 1 Upload | 1 | 6 Compliance and Drishti | 2 |
| 2 Team works | 1 | 7 V-CIP | 1 |
| 3 KAM decides | 3 | 8 Settlement Agent | 2 |
| 4 Voice Chase | 1.5 | 9 Close | 0.5 |
| 5 Fixes | 1.5 | **Total** | **13.5** |

Cut Act 4 (play the rehearsal) and Act 7 for a 9-minute version.
