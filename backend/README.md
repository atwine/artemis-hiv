# ARTEMIS-HIV backend (Phase 4)

A FastAPI shell around the visit check in `artemis/`. The Next.js frontend (Phase 5) calls it;
the Streamlit app (`app.py`) keeps working on its own and doesn't use it.

Who may call it: `ACCESS.md` at the repo root, proven by `tests/test_access.py`. In short, only
the app's own pages on this laptop; it listens on 127.0.0.1 and refuses other websites.

## Routes

| Method | Route | What it does |
|---|---|---|
| GET | /api/health | `{"status": "ok"}` |
| GET | /api/patients | the patient list (from `Data/mock_patients.json`, `Data/custom_patients.json` and `Data/demo_day_patients.json`, read only) |
| POST | /api/patients | add a new made-up case (201), written where the Streamlit app keeps added cases; an ID in use is 409; the form's rules (`artemis/patient/new_case.py`) |
| GET | /api/patients/{patient_id} | one patient's record; `labs` maps each test to its results, each with `date`, `value`, `unit` and `source` in the unit it was recorded in (never converted); typed-in lab text comes apart as `lab_notes` |
| POST | /api/patients/{patient_id}/visits | run the visit check: `{"note": "...", "use_ai": true, "include_plan": false}`; alerts come back as CDS Hooks cards and the run is saved |
| POST | /api/visits/{visit_id}/decisions | acknowledge or override alerts: `{"decisions": [{"alert_id": "...", "action": "Override", "reason": "Other (say why)", "comment": "..."}]}`; reasons are `artemis/review.py` `OVERRIDE_REASONS`; the reply says `finalized_at` (null while open) |
| POST | /api/visits/{visit_id}/finalize | finalize once every alert is decided (422 with `FINALIZE_BLOCKED` otherwise); again with nothing changed returns the same; a later decision reopens the visit |
| GET | /api/visits/{visit_id} | reopen a saved visit as it was shown, with its note, decisions and `finalized_at`; no new AI call |
| GET | /api/patients/{patient_id}/visits | a patient's saved checks, newest first |
| GET | /api/clinic-day | the demo day board (`Data/demo_clinic_day.json`): each booking with `state` waiting / needs_you / done from the patient's latest check, and the header counts |

The API's published shape is saved in `docs/api/openapi.json` (the website builds its types from
it); `tests/test_openapi_snapshot.py` fails when it changes by accident. After a deliberate change:
`python scripts/export_openapi.py`, with the locked package versions, and commit the new file.

The replies carry the screen's own words from `artemis/screen_text.py` (plan item 4.7,
`docs/screen-checklist.md`), so the website only displays them: `banners` (level and text),
`disclaimer` and `finalize_note` on a visit check; `heading`, `references_heading` and
`references` on each card's `extension`, with `values` (the patient values the alert is about:
label, value, unit, date) and `key_sentence` (the closest guideline sentence, or null); `citation` (for example "Uganda HIV Guidelines 2022 ·
p. 255") on each passage; `finalize_note` on a decision reply until every alert is decided.

A card's `uuid` is unique per visit (`<visit_id>:<alert_id>`); decisions use the alert's own id,
`extension.alert_id`. With no database set up, a visit check is refused (503) before any model
call, since nothing could be saved or decided on. If saving fails partway, the results still
come back with `record_saved: false`, as on the Streamlit screen.

With the server running, `http://127.0.0.1:8000/docs` lists every route and its fields. Its
"Try it out" works for GET routes; POSTs from that page are refused, because the access rules
allow only the frontend's address (ACCESS.md).

## Settings (`.env`)

| Setting | Default | Meaning |
|---|---|---|
| `ARTEMIS_DATABASE_URL` | none | the visit-record database, e.g. `postgresql+psycopg://artemis:<password>@127.0.0.1:5434/artemis` |
| `ARTEMIS_API_HOST` | `127.0.0.1` | where it listens; `0.0.0.0` would open it to the Wi-Fi (ACCESS.md says no) |
| `ARTEMIS_API_PORT` | `8000` | |
| `ARTEMIS_API_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | the frontend's address; every other web page is refused |
| `LLM_BASE_URL`, `LLM_MODEL`, ... | | the model server, as for the Streamlit app |

## Run it

```
python -m alembic -c backend/alembic.ini upgrade head     # create or update the tables
python scripts/import_visit_records.py                   # copy the Phase 1 visit-record files in (safe to rerun)
python -m backend                                        # serve on 127.0.0.1:8000
```

`python -m backend` reads `.env` first. Running uvicorn by hand needs the settings in the
environment and `uvicorn backend.main:create_app --factory --host 127.0.0.1`.

The database itself: `docker compose -f backend/docker-compose.yml --env-file .env up -d`
(needs `ARTEMIS_DB_PASSWORD` in `.env`; Docker Desktop must be open).

The first visit check sets up the guideline search (`artemis/config.py`): it loads the search
model and opens the kept index in `storage/chroma`, embedding only passages it doesn't hold yet
(normally none; `python scripts/build_index.py` builds it ahead of time). The backend doesn't load
the Streamlit app (plan 4C.1).

## Tests

`python -m pytest tests/test_access.py tests/test_api.py tests/test_visit_records_db.py`. They use
a stand-in model and guideline search and an in-memory database, so nothing is downloaded or
spent. `test_on_real_postgres` runs too when `ARTEMIS_TEST_DATABASE_URL` points at a throwaway
Postgres database (it creates and drops the tables there).

## Changing the tables

Edit `backend/records.py`, then
`python -m alembic -c backend/alembic.ini revision --autogenerate -m "what changed"`, read the
new file in `backend/migrations/versions/`, and run the tests:
`test_migrations_build_exactly_the_tables_in_the_code` fails if the two disagree.
