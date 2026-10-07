# Frontend-only preview (no backend needed)

The frontend can show a **recorded, read-only snapshot** of the synthetic Sharma Foods case when there is no backend, so a frontend-only deployment (Netlify, Vercel, GitHub Pages) is still worth opening.

## What works in preview mode
* The KAM dashboard with the five demo cases, and the **Sharma Foods** case: the ten checks with their evidence, the timeline, the stage tracker.
* **Interactive PDF Evidence**: the nine documents (bundled PDFs) with every extracted value boxed on the page.
* **MAF (Merchant Application Form)**: the filled form with sources, confidence and conflicts.
* **Ask this case**: the three suggested questions (and two more) with Cognee's recorded answers and source documents.
* The merchant portal for Sharma Foods and the **Settlements** tab of Annapurna Sweets (the healthy ledger).
* A banner says it is a recorded snapshot.

## What does not work (by design)
Uploading, deleting, approving, Voice Chase, Drishti, V-CIP, running the Settlement Agent. Each is refused with the message "Preview mode: this needs the backend". Any question other than the recorded ones in Ask this case says so.

## How it turns on
* **Automatically:** when the backend cannot be reached at all (a network error). With the backend running, nothing changes and live data is used. A server *error* (HTTP 4xx/5xx) is never replaced by the snapshot.
* **Forced:** build with `VITE_STATIC_DEMO=true` to skip any backend attempt (best for a frontend-only deployment).

## Deploy it
```
set VITE_STATIC_DEMO=true
npm run build          # produces dist/ including dist/demo/snapshot.json and dist/demo/files/*.pdf
```
Upload `dist/` to any static host. Nothing else is needed.

## Refresh the snapshot
After changing the demo documents or the checks, from `backend/`:
```
python scripts/export_static_snapshot.py
```
It uses a throw-away database, the recorded Sarvam results in `demo_cache/` (no Sarvam credit needed) and live Cognee for the Ask answers, takes about 4 minutes, rewrites `public/demo/`, and leaves no Cognee dataset behind. Commit `public/demo/`.

## Honest limits
It is a recording, not the running system: it shows what the pipeline produced for the synthetic pack, not a live run. The documents, checks, form and answers are real outputs; the interaction (upload, calls, shop verification, settlement run) is shown only by the demo video or the running app.
