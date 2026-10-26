# Wanderly — Smart Tourist Management System

A complete mini-project with tourist, guide and administrator workflows, a catalog-grounded **Generative AI trip planner using NVIDIA NIM**, a fictional demo dataset, persistent database storage and Vercel deployment configuration.

**Start here:** [SRS](docs/SRS.md) · [Demo walkthrough](docs/DEMO.md) · [Deploy on Vercel](docs/DEPLOYMENT.md) · [API](docs/API.md) · [Test results](docs/TEST_RESULTS.md)

## Run locally
Requires Python 3.12+. SQLite mode uses only the Python standard library.

```powershell
python manage.py init --demo
python app.py
```

Open **http://127.0.0.1:8000**. On Windows, `start.cmd` starts the server after initial setup. Stop it with Ctrl+C. Data persists in `data/stms.db`. First launch also supplies a small base catalog if you skip initialization; the command above adds the complete dataset.

## Demo accounts and dataset
All demonstration accounts use **Explore@12345**. Every person and transaction in the fixture is fictional.

| Role | Email | Features |
|---|---|---|
| Tourist | tourist@stms.local | Book tours, plan trips, save AI itineraries, review completed tours, request help |
| Guide | guide@stms.local | See assigned reservations, confirm bookings and complete departed tours |
| Admin | admin@stms.local | Manage destinations/departures, view reports/audit and resolve requests |

A fresh full seed contains **11 users, 12 destinations, 60 tours (48 upcoming and 12 historical), 40 bookings, 12 verified reviews, 12 itinerary items and 8 support requests**. The working local database may contain additional records from browser verification. Dates are relative to the first full seed. `fixtures/demo.json` is the editable input; `seed_demo.py` supplies consistent relationships and statuses. Rerunning the seed preserves existing records and does not duplicate its dataset. Use a separate database for a fresh demo rather than deleting existing data.

## Enable Generative AI
1. Copy `.env.example` to `.env` locally. Keep `DATABASE_URL` blank for SQLite and `STMS_SECURE_COOKIE=0` for local HTTP.
2. Set `NVIDIA_API_KEY` in that private file. Optionally set `NVIDIA_MODEL`; the default is `nvidia/nemotron-3.5-lightning-30b-a3b`.
3. Restart `python app.py`, sign in as a tourist, and open **AI planner ✦**.

The server calls NVIDIA's hosted `/v1/chat/completions` endpoint. It sends travel preferences and public catalog descriptions, validates the structured response against catalog IDs, and lets the tourist save the result to their private itinerary. The key is never returned to the browser. Plans do not automatically reserve seats.

Without a key, the interface offers an explicitly labelled **fixed catalog preview**, which is not AI-generated. When a configured provider fails, the app reports the failure rather than silently presenting preview content as AI output. Live provider inference requires a valid key; no key is bundled.

## Deploy on Vercel
Import this repository in Vercel with **Framework Preset: Other** and root directory `.`. The repository supplies `vercel.json`, a Python function at `api/index.py`, a static build script and Python dependencies.

**A hosted PostgreSQL database is required.** Set `DATABASE_URL` in Vercel, initialize the same database using `python manage.py init --demo` from a trusted local terminal, and optionally add `NVIDIA_API_KEY` / `NVIDIA_MODEL` in Vercel's environment variables. See [the exact deployment steps](docs/DEPLOYMENT.md). The app refuses to use a local SQLite file on Vercel; it never silently falls back to temporary storage. Database initialization is explicit and does not run on every request or build.

## Validate
```powershell
python -m unittest discover -s tests -v
python scripts/build.py
node --check static/app.js
```

For PostgreSQL verification, install `requirements.txt` and set `STMS_TEST_DATABASE_URL` to a disposable database. The integration suite creates/drops an isolated test schema. GitHub Actions runs the suite against SQLite and a PostgreSQL 17 service. AI provider responses are mocked in automated tests; no real key or paid request is needed.

## Configuration
Local `.env` values are loaded without overriding existing environment variables. On Vercel, configure variables in the dashboard; `.env` is not uploaded.

| Variable | Purpose |
|---|---|
| DATABASE_URL | PostgreSQL connection URL; blank means local SQLite. Required on Vercel. Use TLS for hosted databases. |
| STMS_DB | Local SQLite path; defaults to `data/stms.db` beside `app.py` |
| STMS_HOST / STMS_PORT | Local bind address/port; defaults to 127.0.0.1:8000 |
| STMS_SECURE_COOKIE | Set 1 for HTTPS hosting. Vercel enables Secure automatically. |
| NVIDIA_API_KEY | Optional server-side NVIDIA key |
| NVIDIA_MODEL | Optional NIM model ID |
| STMS_ADMIN_NAME / EMAIL / PASSWORD | Bootstrap a non-demo admin with `python manage.py init` |
| STMS_TEST_DATABASE_URL | Optional PostgreSQL URL for the automated tests |

## Project layout
```text
app.py                 HTTP API, validation and domain rules
database.py            SQLite/PostgreSQL connection and result adapters
ai_planner.py          NVIDIA NIM request, response validation and explicit preview
config.py              Private local environment loading
manage.py              Initialize/check database and seed demos
seed_demo.py           Idempotent relational sample data loader
fixtures/demo.json     Fictional catalog, users, reviews and support content
api/index.py          Vercel function entry point
vercel.json            Routing, security headers, static build and function limits
scripts/build.py       Prepare public browser assets
static/                HTML, JavaScript and responsive CSS
tests/                 HTTP integration, AI and dataset tests
docs/                  SRS, API, deployment, demo and validation documentation
.github/workflows/     SQLite/PostgreSQL continuous integration
```

## Storage and release scope
Back up local SQLite with `python backup.py backups/stms-backup.db`. For hosted PostgreSQL use your provider's backups or `pg_dump`; use separate databases/branches for preview and production deployments. Transactions and PostgreSQL row locks protect seat capacity; persistent database-backed throttles limit login attempts and AI generations.

This release does not integrate real payments, accommodation/transport inventory, live GPS/weather, SMS/email, emergency dispatch, or password recovery. AI suggestions need human review and do not establish availability or total trip cost. Public demo credentials grant broad access to fictional data; initialize without `--demo` for a non-demo environment. Production hosting still needs an operational review, provider backups and appropriate data-retention decisions.
