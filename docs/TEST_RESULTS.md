# Verification results

Executed on 26 October 2026 on Windows with Python 3.12.

## Automated integration tests
Command: `python -m unittest discover -s tests -v`

**Result: PASS — 9 tests, 8.790 seconds.** Each test performs multiple HTTP requests and assertions against an isolated temporary database.

| Scenario | Result |
|---|---|
| Booking totals, request replay, capacity rejection and cancellation/released seats | Pass |
| Competing 8-seat reservations against a 12-seat departure; exactly one succeeds | Pass |
| Destination deactivation and invalid date validation | Pass |
| Guide lifecycle, early completion rejection and verified review/upsert | Pass |
| Tourist ownership, guide assignment and itinerary privacy | Pass |
| Public filtering, empty budget and static-file allowlist | Pass |
| Registration, duplicate email, login, HttpOnly cookie, logout and expiry | Pass |
| Role restrictions, mutation header/origin checks, numeric validation and login throttling | Pass |
| Support resolution, destination/tour administration, reports and audit records | Pass |

Initial execution exposed an open SQLite handle during Windows temporary-directory cleanup. Connection context managers now close handles after commit/rollback; the complete rerun passed with successful teardown.

JavaScript syntax: `node --check static/app.js` — pass.

## Browser smoke check
Opened the running application at http://127.0.0.1:8000 in the in-app browser. Verified:

- Responsive landing page and catalog rendered at a narrow viewport.
- Tourist sign-in succeeded and displayed the tourist name/role.
- Requesting Backwater Escape created reservation #1 and reduced available seats from 12 to 11.
- My trips displayed the pending reservation, date, one guest and ₹3,499 total, alongside the itinerary form.
- A screenshot is saved as `browser-check.png`.

The local working database retains that demonstration reservation. The packaged source excludes the database.

## Verification limits
No certified accessibility audit, production security penetration test, performance benchmark, cross-browser/device matrix or external integration validation was performed. Guide/admin business behavior is covered by HTTP integration tests; every individual UI form has not been manually exercised. No real payments, external reservations or messages were sent.


## Version 1.1 verification — demo data, AI and deployment preparation
Executed 26 October 2026:
- SQLite: **13 tests passed in 13.439 seconds**.
- PostgreSQL adapter against the local PGlite PostgreSQL-compatible socket server: **13 tests passed in 13.851 seconds**. PGlite is not a hosted production PostgreSQL service; its session/connection model differs. GitHub Actions additionally defines a native PostgreSQL 17 test service.
- Seed repeatability/record preservation, exact fresh-dataset counts, completed-booking review eligibility and no overbooked tours: passed.
- AI preview mode, mocked live model output, catalog-ID validation, provider-error handling, rate limit, plan ownership and duplicate-save prevention: passed.
- Static build `python scripts/build.py`, JavaScript syntax check and Python compile checks: passed.

The PostgreSQL adapter disables named prepared statements to work with transaction poolers. Cloud credentials were not provided; a real Vercel deployment and live NVIDIA inference have not been performed. NVIDIA tests use mocked responses. Later network/sandbox changes blocked further local socket checks; the last completed full-suite results above remain the recorded evidence. The previously saved browser screenshot documents the original release; it is not evidence for the new AI view.
