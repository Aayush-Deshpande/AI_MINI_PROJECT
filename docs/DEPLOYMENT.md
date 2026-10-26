# Deploy Wanderly on Vercel

The web assets are served from Vercel's static output; `/api/*` is rewritten to the Python `BaseHTTPRequestHandler` in `api/index.py`. PostgreSQL stores accounts, sessions, tours, bookings, itineraries, reviews, support, AI plans and throttles across deployments. There is no reliance on a writable function filesystem.

## 1. Prepare a database
Create a PostgreSQL database using a provider such as Neon or Supabase, or a PostgreSQL integration from Vercel's Marketplace. Choose a region close to your Vercel function. Obtain the provider's TLS connection string; a provider-supported pooled URL is appropriate for application requests.

Create separate databases/branches for development, preview and production so preview deployments do not modify production bookings. The app expects a PostgreSQL-compatible database, not a browser-accessible REST-only endpoint.

## 2. Initialize and add dummy data
In a trusted local terminal, inside the cloned repository:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` locally and set `DATABASE_URL` to your actual database connection string. Do not paste it into source code, commit it, or include it in screenshots. Then run:

```powershell
python manage.py init --demo
python manage.py check
```

The initializer applies the schema and imports the fictional dataset atomically. It is safe to rerun. A fresh seed includes the publicly documented demo accounts/password, so use a database intended for demonstrations. It never erases existing user data. The seed marker prevents duplicate imports. It does not automatically roll old dates forward; use the admin scheduling form for new departures.

For a non-demo database, set `STMS_ADMIN_EMAIL`, `STMS_ADMIN_NAME`, and a unique `STMS_ADMIN_PASSWORD` (14–128 characters) privately, then run `python manage.py init` without `--demo`. This creates the schema/admin without the fictional accounts. Provision guide accounts using `python manage.py create-guide --name "Guide Name" --email "guide@example.com"` with `STMS_ACCOUNT_PASSWORD` set privately; account roles cannot be assigned through public registration.

## 3. Import the GitHub repository
In Vercel, select **Add New → Project** and import `Aayush-Deshpande/AI_MINI_PROJECT`.

| Setting | Value |
|---|---|
| Framework Preset | Other |
| Root Directory | `.` |
| Build Command | `python scripts/build.py` (from vercel.json) |
| Output Directory | `public` (from vercel.json) |
| Python | 3.12 (from .python-version) |

Add environment variables for the appropriate deployment environment:

| Variable | Required? | Value |
|---|---|---|
| DATABASE_URL | Yes | Initialized hosted PostgreSQL connection URL with TLS |
| NVIDIA_API_KEY | For live AI | Your private NVIDIA NIM key |
| NVIDIA_MODEL | Optional | `meta/llama-3.1-70b-instruct` or another compatible enabled model |
| STMS_SECURE_COOKIE | Optional on Vercel | `1`; already enforced when VERCEL is set |

Do not set STMS_DB or upload `data/stms.db` to Vercel. Do not add `STMS_ADMIN_PASSWORD` to Vercel unless you separately need an administrative initialization process there; normal function requests never bootstrap accounts.

Click **Deploy**. For CLI deployment, the equivalent is running `vercel` from the repository root after configuring the project/environment. This project does not automatically create external databases or deploy from local tests.

## 4. Verify the deployment
1. Open `/api/health`; expect `{"status":"ok","database":"postgres"}`.
2. Open `/` and check the 12-destination catalog and existing ratings.
3. Sign in with the tourist demo account and verify My trips, Reviews and Support.
4. Create a reservation, reload, and confirm persistence. Redeploy and verify it remains.
5. Sign in as the guide and confirm an assigned pending reservation.
6. Sign in as the admin and inspect booking totals, catalog editing and support resolution.
7. With a configured NVIDIA key, the planner badge says **NVIDIA NIM connected**. Generate a trip, inspect the **Generated with NVIDIA NIM** badge, then save to My trips.

If no key is configured, the planner clearly labels its output as a fixed non-AI preview. A provider/key error is displayed as an error and does not silently downgrade to preview.

## Troubleshooting
| Symptom | Check |
|---|---|
| Database unavailable | DATABASE_URL is present in the selected Vercel environment, TLS/provider access is correct, and psycopg installed successfully. Redeploy after variable changes. |
| Internal error / missing relation | Run `python manage.py init --demo` against the same database URL. Initialization is deliberately not performed on builds or requests. |
| Empty catalog | Production initialization without --demo creates an empty catalog; seed the demo database or create destinations/departures as admin. |
| Login does not persist | Use the HTTPS Vercel URL. Local HTTP needs STMS_SECURE_COOKIE=0. Keep browser cookies enabled. |
| API routes return 404 | Ensure the root directory is the repository root and vercel.json was included. Check the api/index.py function in the deployment. |
| AI preview instead of live model | Set NVIDIA_API_KEY in Vercel and redeploy. Check `/api/ai/config` for configured=true. |
| NVIDIA error or timeout | Confirm API key/model access and provider quota; retry or reduce requested days. The provider timeout is 22 seconds within a 30-second function limit. |

## Operational notes
Use provider backup/snapshot tools for hosted data. Limit database credentials to this application's database. Login throttling is account-keyed and database-backed (10 attempts per five-minute window); AI generation allows 10 requests per signed-in tourist per hour. A failed provider request still counts toward that limit. Password recovery, formal accessibility/security audits and real travel/payment integrations remain outside this release.

References: [Vercel Python runtime](https://vercel.com/docs/functions/runtimes/python), [Vercel storage and SQLite limitations](https://vercel.com/kb/guide/is-sqlite-supported-in-vercel), [NVIDIA NIM chat API](https://docs.api.nvidia.com/nim/reference/meta-llama-3_1-70b-infer).
