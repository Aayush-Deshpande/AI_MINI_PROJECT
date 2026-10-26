# Software Requirements Specification
## Smart Tourist Management System — Version 1.1

Prepared for Ayush • 26 October 2026 • Status: implementation baseline

## 1. Purpose
The Smart Tourist Management System (STMS) lets tourists discover destinations, reserve guided tours, organize travel itineraries, submit reviews, and request assistance. Guides manage assigned reservations; administrators maintain the catalog and resolve requests. This document defines the local and Vercel-ready demonstration release, including optional NVIDIA NIM itinerary generation, its boundaries, data rules, acceptance criteria, and deployment assumptions.

## 2. Scope and boundaries
The deliverable is a responsive browser application, a Python HTTP application server, a SQLite database, automated integration tests, seed data, and operating instructions. Local SQLite mode runs without third-party Python packages; hosted PostgreSQL mode uses psycopg. All catalog data and reviews are local demonstration data. Currency is INR. The application uses dates rather than time-zone-sensitive tour times.

Included: account registration/login/logout, role-based access, destination search/filtering, rule-based recommendations, scheduled tours, capacity-controlled reservations, cancellation, guide confirmation/completion, personal itineraries, verified reviews, support requests, catalog administration, aggregate reporting, fictional relational demo data, optional Generative AI itinerary creation, and serverless deployment support.

Excluded from this release: real payments/refunds, external accommodation/transport inventory, live weather/maps/GPS, passport processing, emergency dispatch, email/SMS, model training and multilingual content. NVIDIA-hosted language-model inference is optional and included in version 1.1. Booking confirmation does not represent a payment or external supplier reservation. These integrations require separate credentials, contracts, and requirements. Support is not an emergency service.

## 3. Stakeholders and roles
| Role | Responsibilities | Access |
|---|---|---|
| Visitor | Explore destinations and tours | Public catalog only |
| Tourist | Plan and manage travel | Own bookings, itineraries, reviews and requests |
| Guide | Deliver assigned tours | Assigned reservations; confirm and complete them |
| Administrator | Maintain operations | Catalog, all reservations, requests and reporting |

Accounts can hold exactly one role. Public registration always creates tourists. A local operator creates the demonstration guide and administrator through initial database seeding. The release does not provide public role changes or account deletion.

## 4. Operating environment and assumptions
Python 3.12+; a modern JavaScript-enabled browser; one application process; writable local storage; and port 8000 by default. SQLite is suitable for this local/small deployment baseline. Production hosting, HTTPS termination, monitoring and disaster recovery are operator responsibilities. The development server binds to loopback by default. No internet connection is necessary after files are obtained.

## 5. Functional requirements
| ID | Requirement and acceptance criterion |
|---|---|
| FR-01 | Visitors can list active destinations and scheduled tours without authentication. Search matches destination names/descriptions/cities; category and maximum price filters narrow the list. |
| FR-02 | A user registers with a name, unique normalized email and password of at least 10 characters. Invalid/duplicate input returns a useful error; passwords are never returned. |
| FR-03 | Login creates an expiring session; logout invalidates it. Invalid credentials produce a generic failure. Authentication failures are rate-limited per client. |
| FR-04 | Server-side checks enforce roles and ownership on every protected operation, independent of visible browser controls. |
| FR-05 | Recommendations rank active destinations by selected category, optional budget, and average review rating. Results are deterministic and explicitly rule-based. |
| FR-06 | A tourist reserves 1–20 seats on a future scheduled tour. Server calculates the amount from the stored price, snapshots it, and rejects insufficient capacity. Repeated submissions with the same request key cannot create duplicate bookings. |
| FR-07 | Tour capacity includes pending, confirmed and completed reservations. Cancelled bookings release capacity. Capacity checks and inserts execute in one write transaction. |
| FR-08 | Tourists see only their own reservations and may cancel pending/confirmed bookings before the departure date. Completed or cancelled reservations cannot be cancelled. |
| FR-09 | Assigned guides and administrators can move pending bookings to confirmed and confirmed bookings to completed. Completion is permitted on/after the tour date. All other transitions fail. Guides cannot manage another guide's tour. |
| FR-10 | Tourists create dated itinerary items with a title, destination and notes, view items in date order, and delete their own items. Items are private and do not reserve inventory. |
| FR-11 | A tourist may review a destination only after a completed booking there. Ratings are integers 1–5; comments are limited to 1,000 characters. One review per user/destination can be updated. |
| FR-12 | Signed-in users submit support subjects and messages and view their own requests. Administrators see all requests and can resolve them with a response. Request status is open or resolved. |
| FR-13 | Administrators create/update destinations, including name, city, category, description and active flag. Inactive destinations disappear from public discovery and cannot receive new reservations. Historical references remain intact. |
| FR-14 | Administrators create dated tours with an existing active destination, registered guide, positive price, and capacity 1–200. Existing tours are immutable in this release to preserve booked terms. |
| FR-15 | Administrators view user, destination and booking counts, total reserved value excluding cancellations, and bookings by status. Reserved value is not collected revenue. |
| FR-16 | Administrative catalog updates and booking status changes append audit records containing actor, operation, target and UTC timestamp. |

## 6. Primary use cases
### UC-01: Discover and reserve
Precondition: an active destination and future tour exist. A visitor searches the catalog, selects a category/budget, and inspects available seats. The visitor registers or signs in, supplies seat quantity and submits. The server verifies account role, tour date, destination activity and capacity. Success creates a pending reservation with immutable unit price and total. Failure leaves no booking behind and displays the reason. The assigned guide can confirm it.

### UC-02: Manage a trip
A tourist adds destination-linked dated itinerary items and deletes unwanted entries. Booking and itinerary data are independent, so modifying a plan never cancels a reservation. The tourist can cancel an eligible reservation; the server releases seats atomically.

### UC-03: Fulfil a reservation and review
An assigned guide views reservations, confirms a pending booking, and marks a confirmed booking complete on/after departure. The tourist then submits a verified destination review. Attempts to review early or act on another user's booking fail.

### UC-04: Operate the catalog
An administrator creates or edits a destination, selects a guide and schedules a tour. Invalid prices, dates, capacities and guide references are rejected. Deactivating a destination prevents discovery and new reservations but retains historical bookings and reviews.

### UC-05: Resolve support
A signed-in user submits a request. An administrator reads the request and records a response, changing its state to resolved. The requesting user can see the response. The interface warns that support does not provide emergency assistance.

## 7. Business rules and lifecycle
Booking lifecycle: `pending → confirmed → completed`; `pending/confirmed → cancelled` before departure. Terminal states cannot be reopened. Dates are ISO `YYYY-MM-DD`, evaluated against the server's local calendar date. Prices are stored as integer paise, rendered as rupees; totals never use client-supplied amounts. Capacity is per scheduled tour. A guide is assigned per tour. All text has server-enforced limits. IDs are positive integers. Foreign keys preserve referential integrity. Deactivation replaces destructive catalog deletion.

## 8. Data model
| Entity | Essential fields / constraints |
|---|---|
| users | id, name, email UNIQUE, salted password hash, role CHECK, created timestamp |
| sessions | hashed token PRIMARY KEY, user FK, expiry timestamp |
| destinations | id, name, city, category, description, active boolean |
| tours | id, destination FK, guide FK, departure date, price_paise > 0, capacity > 0 |
| bookings | id, user FK, tour FK, seats, unit price snapshot, status CHECK, request key; UNIQUE(user, request key) |
| itinerary | id, user FK, destination FK, date, title, notes |
| reviews | user FK, destination FK, rating CHECK 1–5, comment; UNIQUE(user,destination) |
| tickets | id, user FK, subject, message, status, response |
| audit | id, actor FK, action, target, created timestamp |

Relationships: destination 1:N tours; guide 1:N tours; tourist 1:N bookings; tour 1:N bookings; tourist 1:N itinerary entries and tickets; users N:M destinations through reviews. Foreign-key checks are enabled on every connection. SQLite transactions serialize competing reservation writes.

## 9. Interface requirements
The browser presents Discover, My trips, Reviews, Support and a role-specific Operations view. It has consistent navigation, labeled controls, visible success/error messages, keyboard-accessible controls, and layouts that collapse on narrow screens. Empty lists explain that no matching records exist. Currency/date display is explicit. User-entered text is inserted as text or escaped HTML.

HTTP interface uses JSON under `/api/`; request/response bodies are objects. Errors use `{ "error": "message" }` and suitable 400/401/403/404/409/429 codes. Authentication uses an HttpOnly SameSite=Strict cookie. Mutation endpoints require the same-origin `X-STMS-Request` header and reject mismatched Origin values. API details are in `API.md`.

## 10. Non-functional requirements
| ID | Requirement / verification |
|---|---|
| NFR-01 | Passwords use PBKDF2-HMAC-SHA256 with random salts and 310,000 iterations. Tokens have 256 bits of randomness and are stored hashed. Inspect implementation and login tests. |
| NFR-02 | Sessions expire after 12 hours; cookies are HttpOnly/SameSite, with Secure automatically enabled on Vercel. Secure cookies can be enabled for HTTPS hosting. Verify login/logout/expiry behavior. |
| NFR-03 | Parameterized SQL, escaped rendering, bounded JSON bodies (64 KiB), role/ownership checks and restrictive response headers protect the baseline. Negative integration tests cover core boundaries. |
| NFR-04 | Booking writes must never overbook or duplicate an identical submission. Concurrent and replay tests verify this invariant. |
| NFR-05 | Persistent data survives restart. Database backup/restore uses SQLite backup tooling while the app is stopped or SQLite's online backup API. |
| NFR-06 | Target: ordinary catalog/booking requests below 1 second on a modern local workstation with 1,000 tours, excluding password hashing. This is a design target, not a certified benchmark. |
| NFR-07 | Support current mainstream desktop/mobile browsers with responsive CSS; use semantic controls and visible focus. Formal WCAG conformance is not claimed. |
| NFR-08 | Runtime needs only the Python standard library. Configuration is environment-based and documented. No API keys or real personal data are bundled. |
| NFR-09 | Internal errors are logged server-side; clients receive generic errors without stack traces. Administrative actions are auditable in the database. |

## 11. Architecture
Browser HTML/CSS/JavaScript → same-origin JSON HTTP routes → authorization/validation and business rules → SQLite locally or hosted PostgreSQL on Vercel. PostgreSQL row locks serialize booking changes; psycopg disables named prepared statements for compatibility with transaction poolers. The AI planner calls NVIDIA NIM only when a private server-side key is configured. The server serves only explicit static files. No database files are web-accessible. Domain changes are transactional; each request receives its own connection. The server is a local demonstration service, not a hardened public production server.

## 12. Validation strategy and acceptance
Automated tests operate against an isolated temporary database and real local HTTP server. Cover registration/login, duplicate accounts, role isolation, catalog changes, booking totals/capacity/replay, concurrent booking attempts, guide assignment, lifecycle restrictions, cancellation, private itinerary ownership, review eligibility, support resolution, and reports. Run `python -m unittest discover -s tests -v`. A release is accepted when tests pass and a manual browser smoke check confirms usable catalog and login workflows. Record actual execution in `TEST_RESULTS.md`; distinguish unperformed checks.

## 13. Deployment, recovery and maintenance
Run `python app.py`, open the loopback URL, and use the seeded accounts only for evaluation. Database location and port are configurable. Before a real deployment, replace demonstration credentials/data, enable TLS/Secure cookies, put a production HTTP service in front, establish backup retention, add monitoring, and run security/accessibility/load reviews. SQLite backups contain personal data and must be access-controlled. No automated retention/deletion policy is provided; agree one before collecting real user data.

## 14. Risks and limitations
Local calendar dates can differ from a tourist's device; the server is authoritative. No payment means reserved values cannot be treated as revenue. Seed tours are generated relative to first initialization; old installations need new scheduled tours. Login throttling is shared through the database and keyed by normalized account email. AI generation is limited per signed-in account. There is no password reset/email verification or self-service role assignment. Support has no response-time guarantee. These limitations are explicit release boundaries, not hidden external dependencies.

## 15. Traceability
FR-01/05/13/14 → catalog and administration APIs / Discover and Operations UI. FR-02/03/04 → auth middleware and account forms. FR-06–09 → transactional booking endpoints / My trips and guide Operations. FR-10 → itinerary endpoints / My trips. FR-11 → verified review endpoint / Reviews. FR-12 → ticket endpoints / Support. FR-15 → report endpoint / administrator Operations. FR-16 → audit writes. NFR-01–09 → security helpers, schema constraints, response headers, responsive styles, tests and operating documentation.

## 16. Future change control
Payment gateway, map routing, accommodation inventory, notifications, account recovery, localization, and multi-tenant operations require separate versioned requirements and migrations. Any scope change must update this specification, API documentation, implementation and acceptance tests together.


## 17. Version 1.1 — Demo data, Generative AI and Vercel requirements
| ID | Requirement / acceptance |
|---|---|
| FR-17 | An explicit idempotent demo seed adds 11 fictional users, 12 destinations, 60 tours, 40 bookings, 12 eligible reviews, 12 itinerary items and 8 support requests to a fresh database. Dates are relative to first full seeding; repeats preserve existing data and do not duplicate seed records. |
| FR-18 | A signed-in tourist supplies a catalog destination, start date, 1–7 days, budget preference, party size and interests. With NVIDIA_API_KEY configured, the server requests a structured itinerary from NVIDIA NIM. The key never appears in client responses or source control. |
| FR-19 | Model output must contain exactly the requested number of days and valid active catalog destination IDs. Server-generated dates are authoritative. Invalid provider output, authentication errors and timeouts return useful failures. The model cannot create reservations or change records directly. |
| FR-20 | Without a key, the planner offers an explicitly labelled fixed catalog preview; it never claims preview text was generated by an AI model. Configured provider failures do not silently switch to preview. |
| FR-21 | A tourist saves only their own generated plan to a private itinerary. Saving is transactional and idempotent; a repeated save does not create duplicate items. Plans do not reserve tour inventory. |
| FR-22 | Vercel serves static browser assets and a Python API function. All durable data uses a required DATABASE_URL PostgreSQL database. Missing database configuration fails explicitly; local SQLite is not used on Vercel. Initialization is an explicit operator command, not a per-request or build side effect. |
| NFR-10 | Login limits persist in the database across serverless workers: ten attempts per account per five minutes. AI generation allows ten requests per user per hour. Provider requests time out at 22 seconds within a configured 30-second function duration. |
| NFR-11 | AI preferences/public catalog descriptions may be sent to NVIDIA only through the server-side integration. The UI explains this transfer. Account emails, passwords, support requests and private itinerary history are not included in model context. |

Additional entities: `seed_runs` (versioned seed marker), `login_limits` (hashed account key or internal AI user key, attempt count and window start), and `ai_plans` (owner, validated JSON, saved flag and creation timestamp). PostgreSQL is an alternative persistent backend; local SQLite support remains available. Remote initialization uses an advisory transaction lock, while booking/plan mutations use row locks.

AI suggestions are not guarantees of venue availability, opening hours, route timing, emergency information or total trip cost. The interface requires human review and separates itinerary saving from inventory reservations. Automated AI tests use mocked provider responses; live inference acceptance requires a valid owner-provided NVIDIA key. Deployment acceptance additionally requires /api/health reporting postgres and persistence across a redeployment.
