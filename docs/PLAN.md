# Revival plan

Snapshot taken 2026-11-18. Tick a box when its check passes, not when the code is written.
Each item is about one sitting (1 to 2 hours). Decisions are logged in `docs/decisions.tsv`.

## What "done" means

Version 1 of the revival is done when all four are true:

1. A GitHub Pages site shows the new interface replaying at least 10 synthetic visits, using
   outputs generated on the A100, with a "not for clinical use" notice.
2. The README shows a model comparison table on at least 30 clinician-labelled cases, and one
   command (`python scripts/evaluate.py`) reproduces it.
3. Tests pass in GitHub's automatic checks on `development`.
4. Every alert on screen quotes the guideline passage it rests on, with the document and edition.

## Ground rules

- Clinicians are the main user; every screen must also read well as a portfolio piece.
- Model calls go to the vLLM server on the A100 now. OpenRouter models get added for the
  comparison. Ollama comes back only for fine-tuning experiments.
- Synthetic or clinician-written cases only. No real patient records anywhere.
- Out of scope: mixed Luganda/English notes.
- Branch flow: each piece of work gets its own branch off `development`. Once reviewed, it is merged into
  `development` locally and pushed, with no pull request; `development` moves to `staging` the same way.
  The only pull request is `staging` into `main`, and only the owner merges it. Code review and security
  review before anything reaches `development`. Nothing is pushed without a yes.

## Phase 0: Foundations

- [x] 0.1 Rename to `artemis-hiv` (GitHub repo, description, README and on-screen title). Topics still to add.
- [x] 0.2 Commit the vLLM connection work (on `claude/kaggle-project-review-89c107`).
- [x] 0.3 Security scanners: secret scan on every commit, dependency and code scans on every push.
- [x] 0.4 Create `development` and `staging` from `main`; first pull request goes through them.
- [x] 0.5 Fix the 5 failing tests; move the loose `test_*.py` scripts out of the test run; lock package versions.
      Tests fixed (16 pass on GitHub); debugging scripts deleted; packages locked with pip-tools
      (`requirements.in` -> `requirements.txt`).
- 0.6 moved to Phase 2B as 2B.6 (2026-11-25).

Check: tests all pass; both branches exist; scanners run on a pull request.

## Phase 1: Fix everything the audit found

The baseline exposed four faults. The owner then asked for a thorough repair: every function on
the analysis path was read (121 of 121), 225 findings were grouped into 40 root causes, and an
independent rerun confirmed all 48 serious ones. Details: `docs/audit/`. Each fix starts with a
test that fails on the old code, ends with that test passing, and is logged in
`docs/decisions.tsv`, `docs/refactor/moves.tsv` and, for new kinds of failure,
`docs/lessons-learned.md`. Evidence for each fix is in `eval/fixes/`.

- [x] 1.0 Baseline first: a script runs all 7 test patients through the A100 and saves every
      output to `eval/baseline/`. Every fix below is judged against this "before" snapshot.
      Done 2026-11-25: 3 runs per patient; findings in `eval/baseline/README.md`.
- [x] 1.A Audit: read all 121 functions, group the 225 findings into 40 causes, verify the
      serious ones independently, and separate the analysis from the screen (option B).
- [x] Fix 1: delete the AI modes that could no longer run, and the dead copies of the plan screen.
- [x] Fix 2: results belong to the patient and note they were run for (old item 1.3, first half).
- [x] Fix 3: rule alerts are never dropped, and a failed AI review is never green (old item 1.1).
- [x] Fix 4: lab results carry their unit, date and age, and notes are dated.
- [x] Fix 5: drugs are recognised however they're typed, and the rules read the medicine list.
- [ ] Fix 6: no false "missing data" or "no plan" in the summary the AI reads.
- [ ] Fix 7: the management plan shows only what the AI said: no invented "AGREE" or green
      "Continue" (old item 1.2).
- [ ] Fix 8: AI replies are read correctly, and nothing is cut, merged or dropped.
- [ ] Fix 9: save the visit record: reviews, overrides and reasons (old item 1.3, second half).
      9b: reopen a patient's last results from the record, with no new AI call.
- [ ] Fix 10: small fixes, plus two dangerous retrieval faults pulled forward from 2B (the cleaner
      deleting "<50" thresholds, and the backup index keeping only one guideline).
- [ ] 1.Z Rerun the baseline (7 patients, 3 runs each) and compare with `scripts/compare_runs.py`;
      code review, security review, then merge into `development` and push after a yes.

Old item 1.4 (name the real source on each citation) moved into Phase 2B with the other
retrieval work (G32 in `docs/audit/phase1-groups.tsv`), as the owner ruled.

Check: rerun the baseline; the before/after difference shows each fix and nothing unexplained.

## Phase 2: Evaluation and first model comparison

Starts right after Phase 1 and can run alongside Phase 3. It comes before the rebuild because its
numbers decide which parts of the pipeline earn their keep.

- [ ] 2.1 Case set: the 7 existing patients, the clinician-written example outputs and Timothy's
      test cases, then 20 to 30 new short cases written and labelled by clinicians (each lists the
      alerts it should raise and the guideline passages that support them).
- [ ] 2.2 Scoring: for each case, which expected alerts were caught and which alerts were false
      alarms. A model may help match wording, but a person spot-checks its matches. Report three
      numbers, each with how many cases it rests on:
      - sensitivity (recall): of the problems a patient really has, how many the app caught. This is
        "nothing missed", and for a safety tool it matters most.
      - precision: of the alerts the app raised, how many were real problems.
      - specificity: of the patients with nothing wrong, how many the app correctly left clear.
      Working target from the owner: about 85%, to be set per measure with the doctor before the run.
- [ ] 2.2b Write the method down so it can be reported: how many cases, who wrote and labelled
      them, how a raised alert is matched to an expected one, how many runs per case (answers vary
      between runs), and the date and model.
- [ ] 2.3 Run the models: Llama 3.3 70B on the A100 and 2 or 3 OpenRouter models (MedGemma optional,
      as the original competition baseline).
- [ ] 2.4 Results table plus all raw outputs saved (they feed the showcase in Phase 6).
- [ ] 2.5 (suggested) A knowledge check on the HIV questions in AfriMed-QA.

Check: `python scripts/evaluate.py` rebuilds the table from saved outputs.

## Phase 2B: Retrieval (RAG) revamp

The old results were "sometimes good, sometimes bad". This phase finds out why and fixes it,
measuring every change on the Phase 2 cases. Background reading: `docs/research/RAG-OPTIONS.md`.

Retrieval faults found in the Phase 1 audit are fixed here, not in Phase 1 (owner, 2026-11-25).
They are listed in `docs/audit/phase1-findings.tsv` with the target phase `2B`.

- [ ] 2B.1 Retrieval check on its own: for each case, does the right guideline passage come back?
      This separates "looked in the wrong place" from "read the right page and reasoned badly".
- [ ] 2B.2 Try the simplest fixes first (guideline-structure chunks, keyword plus meaning search,
      a re-ranking step), one at a time, keeping each only if the scores improve.
- [ ] 2B.3 Try an agentic loop like PolicyLens: plan the questions, search, judge whether the
      results are good enough, search again if not.
- [ ] 2B.4 Pick the winner on the numbers and write up what was learned (a good demo piece too).
- [ ] 2B.5 Revisit the four accepted chromadb advisories: replace or upgrade Chroma, then remove
      their `--ignore-vuln` lines from `.github/workflows/security-scans.yml`.
- [ ] 2B.7 How the guideline knowledge is stored, decided on the 2B.1 numbers: plain Markdown as
      today, Markdown split along the guideline's own sections, or structured records (JSON, one per
      recommendation, with drug, condition, action, country and edition). Also which search fits
      each: meaning search, keyword search, or both together, and filters by country and edition.
- [ ] 2B.6 Decide where the guideline files live, once 2B has picked the documents and how their text
      is extracted. Today the app searches 4 Markdown files in `Data/MarkDown Files/`; the 3 PDFs in
      `Data/` (28 MB) are unused apart from one PDF-reader test. Options: keep them in the repo, or a setup
      script that downloads them from the official sources. Either way, add a sources list (document,
      edition, official link) for citations. Whether the public repo may hold the guideline text is the
      owner's call.

Check: the retrieval and answer scores before and after each change are in the decision log.

## Phase 3: Designs in Paper

- [ ] 3.1 Design brief: clinicians first; Penda-style red/amber/green; review on the alert itself;
      guideline text beside the patient values.
      Notes from Phase 1: the regimen pick-list should not offer "Select all" (Streamlit adds it);
      lab entry is one row per result with a unit.
- [ ] 3.2 Mock up the visit-review screen three ways (clinic workstation, guided case review,
      evidence-first). You pick.
- [ ] 3.3 Finish the chosen direction: patient list, visit review, plan, audit record, plus colours
      and type as reusable design tokens.

Check: you have picked a direction and signed off the screens.

## Phase 4: Backend (FastAPI)

- [ ] 4.0 Write down who may see and do what (`ACCESS.md`), even for a synthetic-data demo.
- [ ] 4.1 Typed models for patient, alert and plan. Alerts take the CDS Hooks card shape
      (summary, severity, source, suggested actions, override reasons).
- [ ] 4.2 Endpoints: list patients, run a visit check, record acknowledge/override.
- [ ] 4.3 Build the guideline index once and keep it, instead of rebuilding on every start.
- [ ] 4.4 Tests that call the endpoints the way the frontend will.

Check: the evaluation script runs through the API and matches Phase 2's numbers.

## Phase 5: Frontend (Next.js + shadcn)

- [ ] 5.1 Set up the app with the design tokens.
- [ ] 5.2 Visit review screen.
- [ ] 5.3 Patient list and record.
- [ ] 5.4 Plan and audit record views.
- [ ] 5.5 Showcase mode: the same screens read saved outputs instead of calling the API.

Check: a full visit works in Chrome; before/after screenshots against the Streamlit app.

## Phase 6: Showcase on GitHub Pages

- [ ] 6.1 Publish showcase mode as a static site with A100 outputs for at least 10 cases.
- [ ] 6.2 Two or three short explainer videos: the problem, a walkthrough, the evaluation.
- [ ] 6.3 README rewrite: screen recording, results table, limitations, "not for clinical use".
- [ ] 6.4 Clinician trial: once the trial version is up, the doctor working with the owner runs
      the test cases and reports what to improve. Their findings become new Phase 2 cases.

Check: the live Pages link works in a fresh browser with no VPN.

## Phase 7: Stretch, as time allows

- [ ] 7.1 CDS Hooks endpoint (patient-view hook, cards, feedback), so record systems such as
      OpenMRS-based UgandaEMR could call it.
- [ ] 7.2 FHIR import (Patient, Condition, MedicationStatement, Observation), tested on Synthea's
      synthetic HIV patients.
- [ ] 7.3 (suggested) Rules-only mode that works with no model connection (winners of the challenge were offline-first).
- [ ] 7.4 (suggested) "Left in red" view: how often critical alerts are left unresolved (Penda's main lever).

## Ideas borrowed

- Penda Health AI Consult (Nairobi): red/amber/green; only red interrupts; never repeat an
  acknowledged alert; fast replies; adoption came from peer champions and sharing "left in red"
  rates. Its later randomised trial reported no clear improvement in patient outcomes, so claims
  stay modest.
- Kenyan HIV alert trial (Lancet HIV, 2015): override reasons should fit reality, such as
  "done, not documented" and "test unavailable".
- MedGemma Impact Challenge winners: Tracer (diagnosis vs results mismatch, close to our plan-gap
  check), ClinicDx (guideline support inside OpenMRS), and offline-first designs.

## Decisions waiting on you

1. The design direction (after the Phase 3 mockups).
2. Database: Postgres on Neon (your default) or a single SQLite file (simpler for a demo).
3. Which OpenRouter models, and a spending cap.
4. Whether Timothy and Dr Kintu write and label the cases, and how they are credited.
5. Where the explainer videos live (YouTube, or small files in the repo).
6. Whether to mirror this checklist as GitHub issues and milestones.
7. Keep or cut the items marked "(suggested)", which were my additions.
8. The target for each of sensitivity, precision and specificity (owner's working figure: about 85%),
   agreed with the doctor before the evaluation run.
