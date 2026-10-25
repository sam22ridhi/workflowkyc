# Deploying Karyakarta (Supabase + Render, or Netlify for the frontend)

This is the `deploy/supabase` branch. Local development is unchanged (SQLite, local files, optional n8n). Setting two groups of environment variables moves the data to Supabase, so the server itself holds nothing that must survive a restart:

| Part | Local default | Deployed |
|---|---|---|
| Database | SQLite file | **Supabase Postgres** (`DATABASE_URL`) |
| Uploaded files, shop photos | `backend/storage/` | local working copy **plus** a private **Supabase Storage** bucket (`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`) |
| Orchestration | n8n, or the backend's built-in fallback | the backend's built-in fallback (`N8N_FALLBACK_INPROCESS=true`, n8n webhook URLs left empty) |
| Memory and AI | Cognee Cloud, Sarvam | the same (they are already hosted) |
| Frontend | `npm run dev` | static site (Render, Netlify or Vercel) |

How the file storage works: the pipeline, Sarvam and Cognee need real file paths, so every upload is saved to the server's disk and also written through to the bucket. If a file is missing from the disk (a restart, a redeploy), it is downloaded again the first time it is needed. A failed write-through is logged and never fails an upload.

## 1. Supabase (once)
1. Create a project at supabase.com. Note the database password.
2. **Database connection string:** *Connect* > *Transaction pooler* (port **6543**). It looks like `postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres`. Use this one, not the direct 5432 string, because a free server cannot hold many direct connections. The app adds `sslmode=require` and the pooler-safe driver settings itself.
3. **Storage:** create a bucket named `karyakarta-files` and leave it **private**.
4. **Keys:** *Project Settings* > *API*: copy the project URL and the **service_role** key. The service key is server-side only: never put it in the frontend or commit it.

The tables are created by the backend on its first start (`init_db`). On that first start it also creates the five demo cases and the Annapurna settlement merchant with its synthetic ledger, which takes a few seconds against a remote database.

## 2. Backend on Render
1. Push this branch to GitHub.
2. Render dashboard: *New* > *Blueprint*, pick the repo. `render.yaml` defines the backend (Docker, `backend/Dockerfile`) and the frontend (static site).
3. Fill the `sync: false` variables when prompted:

| Variable | Value |
|---|---|
| `DATABASE_URL` | the Supabase transaction-pooler string |
| `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` | from step 1 |
| `SUPABASE_BUCKET` | `karyakarta-files` (already set) |
| `SARVAM_API_KEY`, `SARVAM_API_KEY_NEW_FOR_VOICE`, `SARVAM_AGENT_ID`, `SARVAM_VCIP_AGENT_ID`, `SARVAM_CONNECTION_ID`, `SARVAM_AGENT_PHONE_NUMBER` | your values (the same names as `backend/.env`) |
| `COGNEE_BASE_URL`, `COGNEE_TENANT_ID`, `COGNEE_USER_ID`, `COGNEE_API_KEY` | your values |
| `CORS_ORIGINS`, `PUBLIC_APP_URL` | the frontend's address (step 3), no trailing slash |

4. Check `https://<your-api>.onrender.com/api/health`.

## 3. Frontend
**On Render (same blueprint):** set `VITE_API_URL` on the `karyakarta-web` static site to the backend's public address (`https://<your-api>.onrender.com`, no trailing slash) and trigger a deploy. **On Netlify or Vercel:** import the repo (`netlify.toml` / `vercel.json` are included) and set the same `VITE_API_URL`. `VITE_API_URL` is baked in at build time, so changing it needs a rebuild.

Then go back to the backend and set `CORS_ORIGINS` and `PUBLIC_APP_URL` to the frontend's address and redeploy it. (That two-pass order is unavoidable: each side needs the other's address.)

Because the site is on https, the shop-verification page can use a phone's camera and location without a tunnel.

## 4. After it is up
* `scripts/demo_preflight.py` checks a backend running on this machine, so for a deployed one open `/api/health` and walk the demo in the browser instead.
* Set `CPV_ALLOW_DEMO_REFERENCE=true` on the backend only while you need the demo controls (demo upload, resets, the spike). Leave it `false` for anything public: there is no login.

## Free-tier behaviour to expect
* **Render free:** the backend sleeps after about 15 minutes without traffic and takes about a minute to wake. A background step (an upload being processed) is lost if the service sleeps in the middle of it. A free uptime pinger on `/api/health` keeps it awake during a demo.
* **Supabase free:** a project with no activity for about a week is paused; resume it from the dashboard. Free Postgres has a small size and connection limit (the pool here is 5).
* **Sarvam:** reading a *new* document needs Sarvam credit. Documents with a recorded result (`backend/demo_cache/`, shipped in the image) work without it while `DEMO_MODE=true`.
* **n8n is not deployed here.** The backend runs the same steps itself. To use n8n anyway, run it on a paid always-on service with a volume, import the four workflows from `backend/n8n/`, point their backend address at the API, and set the four `N8N_*_WEBHOOK_URL` variables.

## Running the tests against Postgres
```
docker run -d --name kk_pg -e POSTGRES_PASSWORD=test -e POSTGRES_DB=karyakarta -p 55432:5432 postgres:16-alpine
set TEST_DATABASE_URL=postgresql://postgres:test@localhost:55432/karyakarta
.venv\Scripts\python.exe -m pytest -q
```
Without `TEST_DATABASE_URL` the tests use SQLite and never touch Supabase, whatever is in your `.env`.

## Moving existing local data to Supabase
Not needed for a fresh deployment (the demo data recreates itself). To carry a local case over, re-upload its documents through the app; the database is not migrated row by row.
