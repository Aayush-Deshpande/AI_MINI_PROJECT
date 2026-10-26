# API contract

All endpoints are same-origin. Responses use JSON. Successful operations return HTTP 200; errors return `{ "error": "message" }`. Typical errors: 400 invalid input, 401 login required/invalid credentials, 403 prohibited action, 404 missing record, 409 conflict/invalid transition, 413 excessive body, 415 wrong content type, 429 login throttled, 500 internal failure.

POST/DELETE requests require `X-STMS-Request: 1`. Bodies are JSON objects with `Content-Type: application/json` and a maximum size of 64 KiB. A supplied Origin must match Host. Login sets an HttpOnly, SameSite=Strict cookie; retain it for subsequent requests. No CORS access is enabled. Monetary values are integer paise, except the catalog budget query which is whole rupees. IDs and numeric body fields must be JSON integers, not strings or booleans.

| Method | Path | Access | Body/query | Response |
|---|---|---|---|---|
| GET | /api/me | Public | — | user object or null |
| GET | /api/health | Public | — | status and database type |
| GET | /api/ai/config | Public | — | configured boolean, provider, model (never the key) |
| POST | /api/ai/plan | Tourist | destination_id (0 for all), start_date, days (1–7), budget (INR 1–1,000,000), guests (1–20), interests (1–500 chars) | id, validated plan with mode ai/preview |
| POST | /api/ai/plans/{id}/save | Owner tourist | empty object | message; adds plan days to itinerary once |
| POST | /api/register | Public | name, email, password | message |
| POST | /api/login | Public | email, password | message + session cookie |
| POST | /api/logout | Any | empty object | message + expired cookie |
| GET | /api/catalog | Public | search, category, budget query parameters | destinations, tours |
| GET | /api/bookings | Signed in | — | bookings, restricted to owner/assigned guide; all for admin |
| POST | /api/bookings | Tourist | tour_id, seats (1–20), request_key (8–100 chars) | id, message |
| POST | /api/bookings/{id}/status | Role/ownership checked | status | message |
| GET | /api/itinerary | Tourist | — | own items |
| POST | /api/itinerary | Tourist | destination_id, date, title, notes | message |
| DELETE | /api/itinerary/{id} | Owner | empty object | message |
| GET | /api/reviews | Public | — | reviews with author and destination |
| POST | /api/reviews | Tourist with completed booking | destination_id, rating (1–5), comment | message |
| GET | /api/tickets | Signed in | — | own tickets; all for admin |
| POST | /api/tickets | Signed in | subject, message | message |
| POST | /api/tickets/{id}/resolve | Admin | response | message |
| GET | /api/admin | Admin | — | report, destinations, guides, latest 50 audit entries |
| POST | /api/admin/destinations | Admin | optional id, name, city, category, description, active (0/1) | id, message |
| POST | /api/admin/tours | Admin | destination_id, guide_id, date, price_paise, capacity (1–200) | message |

## Booking example
```json
{
  "tour_id": 1,
  "seats": 2,
  "request_key": "a-unique-random-id-per-reservation"
}
```
The key is scoped to the signed-in user. Replaying identical details returns the original ID, including after cancellation; changing details with the same key returns 409. Use a new key for a new intended reservation. Only future departures at active destinations accept new bookings. The transaction locks before reading capacity and inserting the reservation.

## Status changes
`pending → confirmed` and `confirmed → completed` require the assigned guide or an administrator. Completion requires the departure date to be today or earlier. `pending/confirmed → cancelled` requires the owning tourist or administrator and a future departure. Terminal statuses cannot transition.

## Catalog response
Destinations contain id, name, city, category, description, active and average rating (0 means no ratings). Tours contain id, destination_id, guide_id, date, price_paise, capacity, guide name and available seats. The client associates tours with returned destinations using destination_id. Only future active tours are returned; budget filters their price.

## Validation limits
Names/cities/titles: 100 characters; email: 254; passwords: 10–128 on registration; category: 40; destination description/itinerary notes: 2,000; review comment: 1,000; support subject: 150; support message/response: 3,000. Dates must be canonical ISO YYYY-MM-DD. Empty itinerary notes are allowed. Input strings are trimmed. Booking totals are seats × the stored unit-price snapshot. Client-supplied totals are never used.


## AI planner and deployment notes
The planner is catalog-grounded through the supplied context and server-side validation, not a vector-database retrieval system. A plan response includes id and plan: title, summary, days (day/date/destination_id/destination/city/title/morning/afternoon/evening/notes), packing, mode, provider and model. Mode is ai only for a validated NVIDIA response; mode preview is an explicit fixed local template. Configured provider errors return 502 and no plan is stored. The AI endpoint is limited to ten requests per signed-in tourist per hour; rejected provider attempts also consume an attempt. Saving an owned plan is transactional/idempotent and does not reserve seats.

Login attempts are limited per normalized email to ten in a five-minute window using persistent storage. On Vercel, cookies automatically include Secure. The me response also includes a demo boolean for whether the bundled demo administrator exists. Health reports only status/database type; no connection URL or key is returned.
