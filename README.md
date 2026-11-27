# ARTEMIS-HIV

A clinical decision support demo for HIV care, first built for the Kaggle MedGemma Impact
Challenge (Jan to Feb 2026) and now being rebuilt as a website. The plan is in `docs/PLAN.md`.
Synthetic data only; not for clinical use.

For a clinic's day, the app:
- runs **fixed safety rules** on a patient's record and today's note;
- runs an **AI review** of the same record, which may only raise problems the Ugandan guidelines
  support, citing the passages it read;
- shows each alert with the guideline passages behind it, and asks the clinician to acknowledge
  or override every one before the visit is finalized;
- on request, makes the **AI's management plan** and compares it, item by item, with the
  clinician's own plan ("Compare plans").

Important: this is **decision support only**. Clinicians keep final authority.

## What's in this repo

- **The website**: `web/` (Next.js), in the owner's chosen design; see `web/README.md`
- **The backend**: `backend/` (FastAPI, Postgres); see `backend/README.md`. Who may call it:
  `ACCESS.md`
- **The app's logic**: `artemis/` (patient record, rules, AI review, guidelines, plan, review rules)
- **Search engine and embeddings**: `modules/`
- **Made-up patients and the demo clinic day**: in the database; their backup is
  `backend/seed/patients.sql` (loaded into a new database with `python scripts/patients_backup.py load`)
- **Guideline Markdown files**: the Ugandan guidelines in `Data/MarkDown Files/` (only the files
  registered in `artemis/guidelines/sources.py` are searched); `Data/MarkDown Files/README.md`
  names each document, its edition and where to get the PDF (the PDFs are not in the repository)
- **The kept guideline index (Chroma)**: `storage/chroma/` (built on first use, or ahead of time
  with `python scripts/build_index.py`)
- **Evaluation**: test cases, runs and results in `eval/`

## Prerequisites

- **Python 3.12+** (the locked package versions need it).
- **Node.js** for the website (`web/README.md`).
- **Docker Desktop**, for the Postgres database.
- A model server for the AI review and plans (see "Model server"). Without one, the rule checks
  still run.

## Setup (Windows)

```bash
git clone https://github.com/atwine/artemis-hiv.git
cd artemis-hiv
python -m venv .venv
source .venv/Scripts/activate        # PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Copy `.env.example` to `.env` (git ignores it) and fill it in: the database password and
address, and the model server.

## Run the app

```bash
docker compose -f backend/docker-compose.yml --env-file .env up -d   # the database
python -m alembic -c backend/alembic.ini upgrade head                # create or update the tables
python scripts/patients_backup.py load                               # first time only: the made-up patients and demo day
python -m backend                                                    # the backend, on 127.0.0.1:8000
```

Then, in a second terminal:

```bash
cd web
npm install
npm run dev
```

and open `http://127.0.0.1:3000`. Both listen on this laptop only (`ACCESS.md`).

## Using it

1. The **day board** lists the clinic day's appointments in time order, each with where its
   visit stands. Step to the days before and after with the arrows. **Add a case** books a new
   made-up patient at a time on its visit date.
2. Open a patient. The record is on the left; write today's note on the right.
3. **Run checks**. The fixed rule checks always run; the AI review runs when a model server is
   set. Each alert says whether it came from a rule check or the AI review, with the guideline
   passages behind it. A banner says when the AI review failed or was cut short, so a missing
   AI review never looks like a clean result. Every check is saved; if saving fails, the visit
   says so and its alerts can't be decided.
4. **Acknowledge** or **Override** every alert. An override needs a reason, and "Other (say why)"
   needs a comment.
5. **Compare plans** makes the AI's management plan for the visit and compares each item with
   your note. A plan that passed the app's checks is kept and shown again without a new AI call.
   It is the main button once every alert has an answer; Finalize stays one step away in the tray.
6. **Finalize** saves the visit once every alert is decided. A later decision reopens it.

Checks and plans together are limited to 6 a minute, so a stuck page can't run up the model bill.

## Model server

The backend sends its model calls to any OpenAI-compatible server (vLLM, OpenRouter, or a local
Ollama through its `/v1` endpoint). In `.env`:

- `LLM_BASE_URL`: the server address up to and including `/v1`
- `LLM_MODEL`: the model id (empty means the first model the server lists)
- `LLM_API_KEY`: only if the server checks a key (OpenRouter does)

The address stays in `.env`: replies, error messages and saved records never show it.

## Evaluation (preliminary)

`eval/phase2/README.md` has the method and the first results: 11 test visits with a draft answer
key, run 5 times each on Llama 3.3 70B, DeepSeek V3.2, GLM 5.2 and Claude Haiku 5.5, plus an
AfriMed-QA knowledge check. No clinician has checked the answer key yet, so these numbers are
not the app's accuracy. `python scripts/evaluate.py` rebuilds the table from the saved runs.

New runs go through the backend itself (`backend/evaluation.py`): each case's patient goes into
a throwaway database, then "run checks" and "Compare plans" run as the website presses them.
`python scripts/check_phase4.py` replays GLM's final run that way with its saved replies (nothing
spent) and must give the same alerts, passages and scores. Running new models needs
`OPENROUTER_API_KEY` (set a spending limit on the key) and `HF_TOKEN` (to download AfriMed-QA)
in `.env`, used only by the scripts.

## Saved data

Everything the app saves is in Postgres: the patients, the clinic days and appointments, each
visit check, each decision on an alert, each Finalize and each plan. Rows are only ever added;
a changed mind is a new row, and the latest one counts. The patients' backup is
`backend/seed/patients.sql`; the repo is public, so it holds made-up patients only.

## Tests

```bash
pytest
```

They use a stand-in model and guideline search and an in-memory database, so nothing is
downloaded or spent. Point `ARTEMIS_TEST_DATABASE_URL` at a throwaway Postgres database to run
the real-database tests too. The website's own tests: `web/README.md`. GitHub runs the tests on
every push and pull request.

## Adding or upgrading a package

`requirements.in` lists the packages the app uses directly. `requirements.txt` pins the exact
version of every package, so every install gets the same versions. It was made with pip-tools
on Windows; regenerate it there, not in a Linux container (a Linux lock adds GPU libraries).

```bash
pip install pip-tools
# edit requirements.in, then regenerate the lock:
pip-compile --allow-unsafe --strip-extras --no-emit-index-url --output-file=requirements.txt requirements.in
# to move one package to its newest version:
pip-compile --allow-unsafe --strip-extras --no-emit-index-url --output-file=requirements.txt --upgrade-package fastapi requirements.in
pip install -r requirements.txt
```

## Troubleshooting

### "Guideline search unavailable"

The backend searches the Ugandan guideline **Markdown files** under `Data/MarkDown Files/`
(`artemis/config.py`), only those registered for Uganda in `artemis/guidelines/sources.py`: a
Ugandan clinic gets Ugandan guidance only. `python scripts/check_index_sources.py` checks that
the search database holds Ugandan guidance only. If the search model cannot load, the visit
shows a red banner, the AI review is off and only the rule checks run; "Compare plans" makes no
plan until it loads.

### The first check is slow

The first visit check loads the search model, which may download on first use, and opens the
kept index. `python scripts/build_index.py` builds the index ahead of time. To rebuild it, stop
the backend and delete `storage/chroma/`.

### "The database is not set up"

`ARTEMIS_DATABASE_URL` is missing from `.env`, or the database isn't running (Docker Desktop
open, then the `docker compose` line above). "No clinic day is set up yet" means the backup
hasn't been loaded: `python scripts/patients_backup.py load`.

## Project structure

```text
.
├── web/                    the website (Next.js)
├── backend/                the API (FastAPI), its tables and migrations, the patients' backup
├── artemis/                the app's logic, with no web code
│   ├── patient/            reading a record: labs, medicines, summary, new cases
│   ├── rules/              the fixed safety rules
│   ├── ai/                 the model client and the AI review
│   ├── guidelines/         cleaning, storing and searching guideline text
│   ├── plan/               the AI management plan and how it is read
│   ├── visit.py            one visit check, and the plan step on its own
│   ├── review.py           alert review and Finalize rules
│   ├── screen_text.py      the wording every screen shows
│   └── evaluation/         test cases, scoring, model runs, AfriMed-QA quiz (Phase 2)
├── modules/                embeddings, search engine, fallback explanations
├── scripts/                index, evaluation, backup and checks
├── Data/                   the guideline files
├── docs/                   plan, decisions, design, screen checklist, code map
├── eval/                   baseline runs, fix evidence, evaluation cases and results
└── tests/
```
