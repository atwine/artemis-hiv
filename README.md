# ARTEMIS-HIV

A clinical decision support demo for HIV care, first built for the Kaggle MedGemma Impact
Challenge (Jan to Feb 2026) and now being rebuilt. The revival plan is in `docs/PLAN.md`.
Synthetic data only; not for clinical use.

This app:
- Runs **deterministic alert rules** on a patient encounter note + structured history.
- Retrieves relevant excerpts from local **guideline Markdown files** via a local vector store.
- Generates a clinician-facing explanation using either:
  - A **local Ollama model** (optional), or
  - A deterministic fallback explanation if Ollama is unavailable.

When enabled, the app can also generate a consolidated clinician-facing management plan called **ARTEMIS Review.**

Important: This is **decision support only**. Clinicians retain final authority.

## What’s in this repo

- **Streamlit app**: `app.py`, with screen helpers in `ui/`
- **The app's logic**: `artemis/` (patient record, rules, AI review, guidelines, plan, visit record)
- **Search engine and embeddings**: `modules/`
- **Synthetic demo patients**: `Data/mock_patients.json`; cases you add go to `Data/custom_patients.json`
- **Saved visits**: `Data/visit_records/`, one file per patient (created when you run checks; git ignores it)
- **Guideline Markdown files**: the Ugandan guidelines in `Data/MarkDown Files/` (only the files registered in `artemis/guidelines/sources.py` are searched)
- **Guideline sources**: `Data/MarkDown Files/README.md` names each document, its edition and where to get the PDF (the PDFs are not in the repository)
- **Persistent local vector DB (Chroma)**: `storage/chroma/` (created at runtime)
- **Candidate rules output**: `Data/candidate_rules.json` (created when you click “Mark as candidate deterministic rule”)

## Prerequisites

- **Python 3.12+** (the locked package versions need it; numpy 2.5 requires 3.12).
- A working Python environment with `pip`.
- (Optional) **Ollama** installed locally for LLM-generated explanations.

## Clone the repository

Choose a local folder where you want the project to live (for example: `C:\Users\<you>\OneDrive\Desktop\`). Then:

```bash
git clone https://github.com/atwine/artemis-hiv.git
```

This creates a new folder named `artemis-hiv/` containing the app.

## Setup (Windows)

### Option A: Git Bash

```bash
python -m venv .venv
source .venv/Scripts/activate

python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Option B: PowerShell

```powershell
py -m venv .venv
\.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Run the app

```bash
streamlit run app.py
```

Then open the local URL Streamlit prints (usually `http://localhost:8501`).

### The new website (in progress)

The Streamlit app is being rebuilt as a FastAPI backend (`backend/`) and a Next.js website
(`web/`), in the chosen design. With the backend running (`python -m backend`, see
`backend/README.md`):

```bash
cd web
npm install
npm run dev
```

Then open `http://127.0.0.1:3000`. Running it, its tests and its generated API types:
`web/README.md`.

### How to use the workflow

1. Select a patient. **Patient Details/History** shows the record, including dated lab results.
2. Write today's **Clinician's Assessment & Plan** (optional).
3. Click **Save encounter (run checks)**. The fixed rule checks always run; the AI review runs
   when a model server is set. The run is saved to the patient's visit record.
4. Read the results. Each alert says whether it came from a **Rule check** or the **AI review**.
   A banner says when the AI review failed or was cut short, so a missing AI review never
   looks like a clean result.
5. With **Enable agentic ARTEMIS Review** ticked (Advanced settings), **Output** shows the AI's
   management plan next to your own.
6. Under **Review Alerts**, set **Acknowledge** or **Override** for every alert. An override
   needs a reason, and the reason **Other** needs a comment.
7. **Finalize / Close visit** saves your decisions to the visit record. It is disabled until
   every alert is reviewed.
8. When you come back to a patient, **Show last saved results** reopens the last run without
   asking the AI again. If today's note differs from the saved one, the screen says so.

## Model server

The app sends its model calls to any OpenAI-compatible server (vLLM, OpenRouter, or Ollama's
`/v1` endpoint). Copy `.env.example` to `.env` (git ignores it) and set:

- `LLM_BASE_URL`: the server address up to and including `/v1`
- `LLM_MODEL`: the model id (empty means the first model the server lists)
- `LLM_API_KEY`: only if the server checks a key (OpenRouter does)

The settings panel shows which kind of server and which model are in use, but never the
server's address, which stays in `.env`. If `LLM_BASE_URL` is empty, the app falls back to a
local Ollama server, as described below.

## Evaluation (preliminary)

`eval/phase2/README.md` has the method and the first results: 11 test visits with a draft answer
key, run 5 times each on Llama 3.3 70B, DeepSeek V3.2, GLM 5.2 and Claude Haiku 5.5, plus an
AfriMed-QA knowledge check. No clinician has checked the answer key yet, so these numbers are
not the app's accuracy. `python scripts/evaluate.py` rebuilds the table from the saved runs.
Running new models needs two more settings in `.env`, used only by the scripts:
`OPENROUTER_API_KEY` (set a spending limit on the key) and `HF_TOKEN` (to download AfriMed-QA).

## Saved data

- `Data/custom_patients.json`: cases added with **Add patient case**. If the file can't be
  read, the app says so and won't add or delete cases until it is fixed, rather than
  overwriting it.
- `Data/visit_records/`: one file per patient, one line per event (checks run, visit
  finalized). The lines hold the clinician's notes, so the folder stays on this computer and
  git ignores it. The full-stack rebuild moves these into Postgres (plan item 4.5).

Two optional settings move these files, for example for tests (the test suite does this
itself): `ARTEMIS_CUSTOM_PATIENTS_PATH` and `ARTEMIS_VISIT_RECORDS_DIR`.

## Local LLM (Ollama) fallback

Without `LLM_BASE_URL`, the app can use Ollama for explanation generation.

1. Install and start Ollama.
2. Pull the model:

```bash
ollama pull aadide/medgemma-1.5-4b-it-Q4_K_S
```

3. Run the app and keep **Use the LLM for screening and explanations (if available)** enabled in the UI.

### Model selection

By default the app uses:
- `aadide/medgemma-1.5-4b-it-Q4_K_S` (`artemis/ai/client.py`, `OllamaConfig`)

To override the model without changing code:

```bash
export OLLAMA_MODEL="<your-model-tag>"
```

On PowerShell:

```powershell
$env:OLLAMA_MODEL = "<your-model-tag>"
```

If Ollama is not available or the model is missing, the app falls back to a deterministic explanation.

## Tests

```bash
pytest
```

GitHub runs the same tests on every push and pull request.

## Adding or upgrading a package

`requirements.in` lists the packages the app uses directly. `requirements.txt` is generated from it by pip-tools and pins the exact version of every package, so every install gets the same versions. Don't edit `requirements.txt` by hand.

```bash
pip install pip-tools
# edit requirements.in, then regenerate the lock:
pip-compile --allow-unsafe --strip-extras --no-emit-index-url --output-file=requirements.txt requirements.in
# to move one package to its newest version:
pip-compile --allow-unsafe --strip-extras --no-emit-index-url --output-file=requirements.txt --upgrade-package streamlit requirements.in
pip install -r requirements.txt
```

## Troubleshooting

### “Guidelines PDF not found”

The app expects the Ugandan guideline **Markdown files** under `Data/MarkDown Files/`
(`GUIDELINE_MD_DIR` in `app.py`). It searches only the files registered for Uganda in
`artemis/guidelines/sources.py`: a Ugandan clinic gets Ugandan guidance only, so another file in
the folder is ignored. The South African and WHO guidelines are not in the repository (they
stay on the owner's computer). `python scripts/check_index_sources.py` checks that the search
database holds Ugandan guidance only.

If you add or change guideline files, restart Streamlit: a changed file gets a fresh search
index. If the search model cannot load, the screen says so in red and the AI review is off for
the visit; only the rule checks run.

### First run is slow

The first run may be slow because:
- The embedding model may download on first use.
- The guideline Markdown files may be chunked and indexed into a local vector store.

### “Ollama unavailable” or no LLM explanation

- Confirm Ollama is installed and running.
- Confirm the model exists:

```bash
ollama list
```

If the model tag differs, set `OLLAMA_MODEL` as shown above.

### Reset the local vector DB

Chroma persists locally under:
- `storage/chroma/` (`artemis/guidelines/vector_store.py`)

To rebuild the index, stop the app and delete `storage/chroma/`.

## Project structure

```text
.
├── app.py                  the Streamlit screen
├── ui/                     screen helpers (banners, references, review, saved state)
├── artemis/                the app's logic, with no screen code
│   ├── patient/            reading a record: labs, medicines, summary, saved cases
│   ├── rules/              the fixed safety rules
│   ├── ai/                 the model client and the AI review
│   ├── guidelines/         cleaning, storing and searching guideline text
│   ├── plan/               the AI management plan and how it is shown
│   ├── visit.py            runs one visit check from start to finish
│   ├── review.py           alert review and Finalize rules
│   ├── visit_record.py     the saved visit record
│   └── evaluation/         test cases, scoring, model runs, AfriMed-QA quiz (Phase 2)
├── modules/                embeddings, search engine, fallback explanations
├── scripts/                baseline and evaluation runs, results table, code map check
├── Data/                   demo patients, guideline files, saved cases and visits
├── docs/                   plan, decisions, audit, lessons learned, code map
├── eval/                   baseline runs, Phase 1 fix evidence, Phase 2 cases and results
└── tests/
```

## Debug / developer notes

- To show the hidden debug panel for the agentic planner, set `AGENTIC_RAG_DEBUG=1` before starting the app.
