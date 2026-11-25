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

- **Streamlit app**: `app.py`
- **Core modules**: `modules/`
- **Synthetic demo patients**: `Data/mock_patients.json`
- **Guideline Markdown files**: `Data/MarkDown Files/*.md`
- **Local guideline PDFs (optional / legacy)**: `Data/*.pdf`
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

### How to use the workflow

1. Select a patient.
2. Edit the **Today’s encounter note** (optional).
3. Click **Save encounter (run checks)**.
4. Open **Output**.
5. If alerts are present, use **Select alert** to choose one.
6. Review the alert content (and the **ARTEMIS Review.** plan when enabled).
7. Near the bottom, set **Acknowledge / Override** for the selected alert:
   - **Acknowledge**, or
   - **Override** (requires an override reason).
8. **Finalize / Close visit** is disabled until all alerts are reviewed.

## Model server

The app sends its model calls to any OpenAI-compatible server (vLLM, OpenRouter, or Ollama's
`/v1` endpoint). Copy `.env.example` to `.env` (git ignores it) and set:

- `LLM_BASE_URL`: the server address up to and including `/v1`
- `LLM_MODEL`: the model id (empty means the first model the server lists)
- `LLM_API_KEY`: only if the server checks a key (OpenRouter does)

The settings panel shows which server and model are in use. If `LLM_BASE_URL` is empty, the app
falls back to a local Ollama server, as described below.

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

The app expects guideline **Markdown files** under:
- `Data/MarkDown Files/*.md` (`app.py:L58-L63`)

If you add or change guideline files, restart Streamlit.

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
├── app.py
├── Data/
│   ├── mock_patients.json
│   ├── custom_patients.json
│   ├── candidate_rules.json
│   └── MarkDown Files/
│       ├── *.md
│       └── Example Output/
├── modules/
│   ├── alert_rules.py
│   ├── embedder.py
│   ├── explanation_generator.py
│   ├── guideline_processor.py
│   ├── llm_client.py
│   ├── patient_parser.py
│   ├── rag_engine.py
│   └── vector_store.py
├── plans/
│   └── implementation-plan.md
├── storage/
│   └── .gitkeep
└── tests/
    ├── test_alert_rules.py
    ├── test_guideline_processor.py
    └── test_rag_engine.py
```

## Debug / developer notes

- To show the hidden debug panel for the agentic planner, set `AGENTIC_RAG_DEBUG=1` before starting the app (`app.py:L1490-L1494`).
