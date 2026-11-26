# Access rules: ARTEMIS-HIV backend

Last confirmed by the owner on 2026-11-26 (Phase 4, plan item 4.0).

The backend (`backend/`) is a local tool. It has no logins yet and holds only made-up
(synthetic) patients. The rules below are about where a request comes from, not who is logged
in. Logins come with the Next.js frontend (Phase 5), before anyone but the owner uses the app;
this file gets redone then.

## 1. Data

| Data | What it holds | Sensitivity |
|---|---|---|
| patients | the synthetic test patients: notes, lab results, medicines (`Data/mock_patients.json`, `Data/custom_patients.json`) | sensitive: health (synthetic only) |
| visit_records | each visit check that ran (note, alerts, cited passages, AI review outcome) and each acknowledge/override decision | sensitive: health (synthetic only) |
| guidelines | passages from the published Ugandan guidelines, returned inside a visit check's alerts | public |

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

| Role | patients | visit_records | guidelines |
|---|---|---|---|
| local | view(all) | create(all) | view(all) |
| network | - | - | - |
| website | - | - | - |
| anonymous | - | - | - |

Nobody can edit or delete patients or visit records through the backend. Visit records are
written once and never changed: a new decision is a new row, and the latest one counts.
Reading back past visits is not in this round (owner, 2026-11-26).

## 4. Route map

| Method | Route | Data | Action |
|---|---|---|---|
| GET | /api/health | public | - |
| GET | /api/patients | patients | view |
| GET | /api/patients/{patient_id} | patients | view |
| POST | /api/patients/{patient_id}/visits | patients | view |
| POST | /api/patients/{patient_id}/visits | visit_records | create |
| POST | /api/visits/{visit_id}/decisions | visit_records | create |

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
- The owner's own page gets stuck and runs the visit check over and over. Not covered: see
  section 6.

## 6. Open questions for the owner

- No logins yet. Fine while only the owner uses it on this laptop with synthetic patients;
  logins (better-auth in the Next.js app) must come before anyone else uses it, and this file
  gets redone then.
- Repeated visit checks: no request limit yet (owner, 2026-11-26: note it, add the limit
  before anyone else uses the app). OpenRouter's spending cap is the backstop meanwhile.
- If real patient data were ever used: which law applies (Uganda's Data Protection and Privacy
  Act, 2019 is the likely one), whether consent must be recorded, how long visit records are
  kept, and whether notes may go to a third-party model API outside Uganda (OpenRouter does
  today, with synthetic notes). Owner to decide, with legal advice. Until then: synthetic only.
- Override reasons are today's list ("Already addressed", "Not applicable", "Will address
  later", "Patient declined", "Other"). The plan's "Ideas borrowed" suggests adding "done, not
  documented" and "test unavailable"; a clinical call for Phase 7 with the doctor.

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
