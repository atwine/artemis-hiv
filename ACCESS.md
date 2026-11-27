# Access rules: ARTEMIS-HIV backend

Last confirmed by the owner on 2026-11-26 (Phase 4, plan item 4.0; step 2 routes and the add-case
form's pick lists added the same day).

The backend (`backend/`) is a local tool. It has no logins yet and holds only made-up
(synthetic) patients. The rules below are about where a request comes from, not who is logged
in. Logins come with the Next.js frontend (Phase 5), before anyone but the owner uses the app;
this file gets redone then. Every route's rule also gets redone if the backend is ever deployed
off this laptop (for example to Railway): "this laptop only" means nothing on a server (owner,
2026-11-26).

## 1. Data

| Data | What it holds | Sensitivity |
|---|---|---|
| patients | the synthetic test patients: notes, lab results, medicines, past ART, visits. In the database since plan 4C.2 (tables `patient`, `patient_medicine`, `art_history`, `lab_result`, `lab_note`, `clinical_note`, `encounter`), loaded into a new database from the backup `backend/seed/patients.sql` by `scripts/patients_backup.py load` on this laptop. The demo answer keys stay with the evaluation, not in these tables | sensitive: health (synthetic only) |
| visit_records | each visit check that ran (note, alerts, cited passages, AI review outcome), each acknowledge/override decision, each Finalize, and each AI management plan "Compare plans" made (tables `visit_check`, `alert_decision`, `visit_finalize`, `visit_plan`); rows are only ever added | sensitive: health (synthetic only) |
| guidelines | passages from the published Ugandan guidelines, returned inside a visit check's alerts | public |
| clinic_day | the clinic days and their appointments: made-up clinic, room, clinician, date, appointment times and patient ids. In the database since plan 4C.3 (tables `clinic_day`, `appointment`); the demo day is loaded from the backup with the patients | internal (synthetic only) |
| form_choices | the add-case form's pick lists: ART combinations and drugs, lab tests with their names and units, visit types (from the code) | public |

## 2. Roles

| Role | Who they are | Scope |
|---|---|---|
| local | the owner, through the app's own pages (or a script) on this laptop | all: every row |
| network | another device on the same Wi-Fi or LAN, or the internet if a port is forwarded | none |
| website | any other web page open in the owner's browser, calling the backend in the background | none |
| anonymous | same as network and website: there are no accounts, so anyone who isn't `local` is this | none |

How each is told apart, before any route runs (`backend/access.py`):

- `network` never reaches the backend: it listens on `127.0.0.1` only (`ARTEMIS_API_HOST`,
  default `127.0.0.1`). Opening it to the Wi-Fi is a deliberate change of that setting.
- `website`: any request whose `Origin` header is not one of the app's own pages
  (`ARTEMIS_API_ORIGINS`, default `http://localhost:3000,http://127.0.0.1:3000`) is refused
  with 403. CORS lists the same exact origins, never `*`.
- DNS rebinding (a website that makes its own name point at 127.0.0.1): any request whose
  `Host` is not `localhost` or `127.0.0.1` is refused with 403.

## 3. Permission grid

| Role | patients | visit_records | guidelines | clinic_day | form_choices |
|---|---|---|---|---|---|
| local | view(all), create(all) | view(all), create(all) | view(all) | view(all), create(all) | view(all) |
| network | - | - | - | - | - |
| website | - | - | - | - | - |
| anonymous | - | - | - | - | - |

The pick lists hold nothing private, but they follow the same rule as every other route
except the health check (owner, 2026-11-26: "A, this laptop only"), so there is one rule to
keep track of.

Nobody can edit or delete patients, visit records or the schedule through the backend
(owner, 2026-11-26): there are only GET and POST routes, and a whole visit (add a case, check,
decide, change a decision, finalize, plan, reopen) sends the database no UPDATE or DELETE
(`tests/test_access.py`, plan 4C.7). Every table belongs to a data kind in
section 1, so a new table has no rules until it is added there. Visit records are written once and never changed: a new decision is a new
row, and the latest one counts. Adding a patient adds a new case only: an id already in use is
refused, and each case has size limits.

The clinic day moved into the database on 2026-11-27 (owner: "A, yes as written"): an appointment
is made only by adding a case, in the same save, at the time given on its visit date; a date with
no clinic day gets one then, with the demo day's clinic, room and clinician. That is clinic_day's
only create. Nobody moves, cancels or deletes an appointment, or changes a day's clinic, room or
clinician, through the backend (on the Later list).

The AI management plan ("Compare plans", 2026-11-27) is a visit record with the visit check's
rules: made only for a saved visit, only from this laptop, saved as a new row and never changed.
A plan that passed the app's checks is shown again with nothing run; a failed or flagged one may
be tried again (owner: "A, keep a good plan"). Making one counts toward the visit checks' limit (owner: "A, one shared
limit").

Patients moved into the database on 2026-11-27 with the same rules (owner: "A, keep the rules"):
the backend reads and adds them only there, adding a case is one database save, and nothing in
the backend edits or deletes a patient row.

## 4. Route map

| Method | Route | Data | Action |
|---|---|---|---|
| GET | /api/health | public | - |
| GET | /api/patients | patients | view |
| GET | /api/patients/{patient_id} | patients | view |
| POST | /api/patients/{patient_id}/visits | patients | view |
| POST | /api/patients/{patient_id}/visits | visit_records | create |
| POST | /api/patients/{patient_id}/visits | guidelines | view |
| POST | /api/visits/{visit_id}/decisions | visit_records | create |
| POST | /api/visits/{visit_id}/finalize | visit_records | create |
| GET | /api/visits/{visit_id} | visit_records | view |
| GET | /api/visits/{visit_id} | guidelines | view |
| POST | /api/visits/{visit_id}/plan | visit_records | create |
| POST | /api/visits/{visit_id}/plan | patients | view |
| POST | /api/visits/{visit_id}/plan | guidelines | view |
| GET | /api/patients/{patient_id}/visits | patients | view |
| GET | /api/patients/{patient_id}/visits | visit_records | view |
| POST | /api/patients | patients | create |
| POST | /api/patients | clinic_day | create |
| GET | /api/clinic-day | clinic_day | view |
| GET | /api/clinic-day | patients | view |
| GET | /api/clinic-day | visit_records | view |
| GET | /api/form-choices | form_choices | view |

`POST /api/patients/{patient_id}/visits` runs the visit check. It can call the AI model, which
can cost money on OpenRouter. Its replies carry guideline passages (`guidelines`, view).

## 5. Abuse cases

- A website open in the browser starts a visit check in the background, spending model money.
  Covered by: grid row website = `-`; the `Origin` check refuses it (403) before the route runs,
  and JSON bodies need a CORS preflight that only the app's own pages pass.
- The same website sends the check as a plain-text or form POST (which browsers send without
  a preflight). Covered by: the `Origin` check (403); the route also accepts only JSON.
- A website reads the patient list with a background GET. Covered by: the `Origin` check (403),
  and CORS gives no `access-control-allow-origin` for a foreign origin.
- DNS rebinding: a website points its own name at 127.0.0.1 so the browser thinks the backend
  is the same site. Covered by: the `Host` check (403) before any route runs.
- A phone or laptop on the same Wi-Fi calls the backend. Covered by: listening on 127.0.0.1
  only; `tests/test_access.py` checks the default.
- Someone changes the patient id in the address to one that doesn't exist, or to `../` tricks.
  Covered by: the id must match a loaded patient (404 otherwise); visit records are rows in the
  database, not files named after the id.
- A decision is sent for an alert that isn't in that visit, or an override with no reason, or
  "Other" with no comment. Covered by: refused (422), same rules as today's Finalize.
- A request sends fields the screen doesn't show (for example `"source": "rule"` on a
  decision). Covered by: the request models forbid unknown fields (422).
- A website adds a made-up patient case in the background, or finalizes a visit. Covered by:
  grid rows website = `-`; the `Origin` check refuses it (403) before the route runs.
- A new case reuses an existing patient id to overwrite or shadow a case. Covered by: refused
  (409); cases are only ever added.
- A stuck page sends a huge case (thousands of lab rows, megabytes of text). Covered by: the
  case's size limits (422).
- Two adds with the same new id arrive at once. Covered by: the database refuses the second
  (the id is the table's key), answered as 409; nothing of the second case is saved.
- The backup is loaded twice, or loaded into a database that holds other patients. Covered by:
  `scripts/patients_backup.py load` skips rows already there and refuses a database holding
  patients the backup doesn't have; it is a command on this laptop, never a route.
- A stuck page adds case after case, each opening a clinic day on a new date. Covered by: each
  add is one case with its size limits; a day is opened only by a case booked on it, and the board
  shows one day at a time.
- An appointment is moved or cancelled through the website. Covered by: there is no route that
  does it; the only booking is the one adding a case makes.
- Someone on the Wi-Fi connects to the database directly. Covered by: Docker publishes Postgres
  on 127.0.0.1 only (`backend/docker-compose.yml`).
- Finalize is sent twice, or before every alert is decided. Covered by: a second Finalize
  returns the first one's result without saving again; an unfinished visit is refused (422).
- Someone reopens a visit by guessing its id. Covered by: visit ids are random (uuid4), and an
  unknown id is 404; there is only one role that may read visits anyway.
- The owner's own page gets stuck and runs the visit check over and over. Covered by: at most
  6 visit checks a minute (`ARTEMIS_VISIT_CHECKS_PER_MINUTE`); the next is refused (429) before
  anything runs or is spent (owner, 2026-11-26; `tests/test_check_limit.py`).
- A website presses "Compare plans" in the background, spending model money. Covered by: grid
  row website = `-`; the `Origin` check refuses it (403) before the route runs.
- A stuck page presses "Compare plans" over and over. Covered by: a plan that passed its checks is
  shown again with nothing run or spent; making a plan counts toward the same 6 a minute as visit
  checks (429; `tests/test_compare_plans.py`).
- A plan is asked for a visit that doesn't exist, or while the guideline search is down. Covered
  by: 404 for an unknown visit, 503 with the search down; nothing runs or is saved.
- A failed plan's error shows server details (an address, a stack trace). Covered by: the reply
  says only "The management plan could not be produced."; the row keeps the error's kind only.

## 6. Open questions for the owner

- No logins yet. Fine while only the owner uses it on this laptop with synthetic patients;
  logins (better-auth in the Next.js app) must come before anyone else uses it, and this file
  gets redone then.
- Repeated visit checks: decided 2026-11-26, at most 6 a minute (section 5). Kept in memory,
  so it resets when the server restarts; revisit with logins (a limit per user).
- If real patient data were ever used: which law applies (Uganda's Data Protection and Privacy
  Act, 2019 is the likely one), whether consent must be recorded, how long visit records are
  kept, and whether notes may go to a third-party model API outside Uganda (OpenRouter does
  today, with synthetic notes). Owner to decide, with legal advice. Until then: synthetic only.
- Override reasons: decided 2026-11-26 (the design's list, `artemis/review.py`
  `OVERRIDE_REASONS`). New decisions must use it; saved ones keep the reason they were saved
  with. The doctor may still revise the list in Phase 7.

## 7. What this file does not cover

- Whether login itself is safe (password storage, sessions, password reset).
- Secrets: API keys or passwords committed to the code.
- Libraries with known security holes.
- Server, database and cloud settings (open database ports, public storage
  buckets, debug mode in production, CORS set to allow every site).
- Attacks on the code itself, such as SQL injection or cross-site scripting.
- Limits on repeated requests (rate limiting).
- Backups and what to do if data leaks.

Use `/security-review`, a secret scanner (gitleaks), a dependency audit
(`pip-audit`, `npm audit`) and, for apps holding sensitive data, a human
penetration test for these.
