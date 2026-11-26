# Revival plan

Snapshot taken 2026-11-18. Tick a box when its check passes, not when the code is written.
Each item is about one sitting (1 to 2 hours). Decisions are logged in `docs/decisions.tsv`.

## What "done" means

Version 1 of the revival is done when all four are true:

1. A GitHub Pages site shows the new interface replaying at least 10 synthetic visits, using
   outputs generated on the A100, with a "not for clinical use" notice.
2. The README shows a model comparison table on at least 30 clinician-labelled cases, and one
   command (`python scripts/evaluate.py`) reproduces it (Phase 7; Phase 2 gives a preliminary one).
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
- [x] Fix 6: no false "missing data" or "no plan" in the summary the AI reads.
- [x] Fix 7: the management plan shows only what the AI said: no invented "AGREE" or green
      "Continue" (old item 1.2).
- [x] Fix 8: AI replies are read correctly, and nothing is cut, merged or dropped.
- [x] Fix 9: save the visit record: reviews, overrides and reasons (old item 1.3, second half).
      9b: reopen a patient's last results from the record, with no new AI call.
- [x] Fix 10: small fixes, plus two dangerous retrieval faults pulled forward from 2B (the cleaner
      deleting "<50" thresholds, and the backup index keeping only one guideline).
- [x] 1.Z Rerun the baseline (7 patients, 3 runs each) and compare with `scripts/compare_runs.py`;
      code review, security review, then merge into `development` and push after a yes.

Old item 1.4 (name the real source on each citation) moved into Phase 2B with the other
retrieval work (G32 in `docs/audit/phase1-groups.tsv`), as the owner ruled.

Check: rerun the baseline; the before/after difference shows each fix and nothing unexplained.

## Phase 2: Preliminary evaluation and model comparison (no doctor needed)

Everything here runs without the doctor (owner, 2026-11-25). The answer key is drafted from the
guidelines and marked "draft, not checked by a clinician", so these numbers steer Phases 2B to 6
but are never quoted as accuracy. The doctor's review and the reportable numbers come in Phase 7.

- [x] 2.1 Case set from what exists: the 7 test patients, the 4 clinician-written example answers
      (each turned into a patient record) and the Mr K.S. case. Done 2026-11-25: 11 cases in
      `eval/cases/`, as example 1 turned out to be P005.
- [x] 2.2 Draft answer key: for each case, the problems it should flag and the guideline passage
      behind each, written from the guidelines and marked as a draft. Done 2026-11-25: 22
      expected problems, must-not and also-fine items.
- [x] 2.3 Scoring script (`scripts/evaluate.py`): runs each case 5 times per model and counts, per
      case, the expected problems caught and missed and the extra alerts. Also the measures that
      need no answer key: the same answer across runs, citations only to passages the AI was
      shown, replies read in full, time and cost per check. It rebuilds the table from saved outputs.
- [x] 2.4 Models (owner, 2026-11-25): Llama 3.3 70B on the A100 (the baseline, free), and DeepSeek
      V3.2, GLM 5.2 and Claude Haiku 5.5 through OpenRouter, all with thinking switched off.
      MedGemma-27B left out (owner). Claude Sonnet 5.5 was dropped after a trial: its thinking
      can't be switched off and filled the app's reply room, so its alert list was cut off and
      one check cost $0.07. OpenRouter spending cap $5: the script estimates the cost before a
      run, stops at the cap and records the real cost of every call.
      Measured: one visit check uses about 3,700 tokens in and 740 out.
- [x] 2.5 AfriMed-QA knowledge check: its infectious-disease questions (539, 184 written by
      experts), HIV-related ones picked out, for every shortlisted model. The download needs its
      terms accepted on Hugging Face. Done 2026-11-25: the 286 multiple-choice questions that are
      infectious disease or mention HIV, for all four models. The dataset card gives CC-BY-SA
      4.0 and the paper says non-commercial, so the data stays out of the repo.
- [x] 2.6 Technical leftovers from Phase 1: temperature 0 or judging over several runs (G38); the
      AI citing a made-up "information_gap" passage instead of no passage. Done 2026-11-25:
      citations can only name passages shown (92% before, 100% after); temperature 0 raised
      Llama's same-answer rate from 85% to 98%. The app now runs at temperature 0 (owner, 2026-11-25).
- [x] 2.7 Write the method and the preliminary results table, both marked preliminary, and save
      every raw output (they feed the showcase in Phase 6). Done 2026-11-25:
      `eval/phase2/README.md`.

Check: `python scripts/evaluate.py` rebuilds the preliminary table from saved outputs.

## Phase 2B: Retrieval (RAG) revamp

The old results were "sometimes good, sometimes bad". This phase finds out why and fixes it,
measuring every change on the Phase 2 cases and their draft answer key. Background reading:
`docs/research/RAG-OPTIONS.md`.

Models for these tests (owner, 2026-11-25, from the Phase 2 results): every change is measured
on GLM 5.2 (the lead) and Llama 3.3 70B on the A100 (the free in-house comparison); DeepSeek
V3.2 (the runner-up) joins at checkpoints and when a change may affect false alarms. Only
made-up patients go to the hosted models.

How it runs (approved by the owner, 2026-11-25): (1) a search test set: a gold guideline quote for
each expected problem, plus about 20 standalone questions; (2) a search checker that runs the
app's own searches with no AI call; (3) baselines before any change; (4) a checkpoint with the
owner on whether Phase 2's misses came from the search or from the AI's reasoning; (5) fixes one
at a time, simplest first, each kept only if the search score improves, with the keep rule written
before the run and a Llama end-to-end check for each kept fix; (6) the owner's decisions on the
numbers; (7) a final check on GLM, Llama and DeepSeek, then the write-up. Results go in
`eval/phase2b/`.

Retrieval faults found in the Phase 1 audit are fixed here, not in Phase 1 (owner, 2026-11-25).
They are listed in `docs/audit/phase1-findings.tsv` with the target phase `2B`.

Where it stands (updated 2026-11-26; every number is in `docs/decisions.tsv` and `eval/phase2b/`):
- Done: the search test set (a gold quote for 17 of the 22 problems, 5 not in any guideline,
  plus 20 standalone questions); the search checker with its self-check; the diagnosis (the
  right passage reached the AI for 3 of 17 problems; caught 98% when shown, 72% when not).
- Done, owner's rule (G32): Ugandan guidance only. Only registered Ugandan files are searched,
  the South African and WHO files are in `Data/Not searched - other countries/`, and the search
  database was rebuilt (`scripts/check_index_sources.py` passes). Questions in the top 5 went
  from 3/20 to 13/20; 10 of 22 problems now have no Ugandan passage.
- Baselines, Uganda only (3 runs per case, temperature 0): the AI's own catches are 59% for
  Llama (69% before, with all four guidelines) and 80% for GLM (84% before).
- Tried and dropped by their own rules: 5a, one search per drug and problem (cases 3/12 against
  4/12); 5c, keyword search beside meaning search (every gold passage now found from its own
  words, but cases 3/12 and questions 10/20).
- Premise check (2026-11-26): searching each problem with its own short description, as if the
  app knew what to look for, finds 6/12 (meaning search) or 7/12 (with keyword search) against
  4/12 for the app's real search. The biggest lever is what the app searches for; 5 problems
  stay missing even then, which the index fixes target. Fix 5c is out of the app again.
- The owner picked the search wording first. Fix 5q (the AI writes the patient's guideline
  questions, each searched for its best 2 passages, up to 10): with Llama writing them, 4/12,
  the same as today (generic questions); with GLM, 6/12, one short of the bar of 7 but equal to
  the best this index allows even with perfect wording. Kept by the owner's decision
  (2026-11-26). Second check running: GLM end to end, 3 runs per case, must keep its own catches
  at or above 80%.
- Fix 5b (pieces cut along the guideline's own sections, labelled with the section path, tables
  by whole rows) tried and dropped by its rule: self-check 30/34 and ideal searches 7/12 rose,
  but standalone questions fell to 11/20 and cases to 5/12. The converted files miss some
  headings, so some tables carry the wrong section label. The checker now also measures each
  problem searched with its own description (the ideal-description track).
- Fix 5q's second check passed: GLM end to end with the question step keeps its own catches at
  80% (no gain yet; the passages it finds still mostly miss the rule).
- With the owner's small download pair (2026-11-26), both tried and dropped by their rules,
  measured with GLM's saved questions replayed (the replay reproduced earlier numbers exactly):
  5d, search model bge-small-en-v1.5 (self-check 32/34, cases 7/12, ideal 7/12, but standalone
  questions 11/20); 5e, re-ranker ms-marco-MiniLM-L6-v2 (self-check 34/34, cases 7/12, ideal
  7/12, but questions 10/20). Three fixes in a row helped the patient tracks and hurt the
  standalone questions; read by hand, the lost questions' passages are really wrong (the
  web-trained models lack the medical knowledge the clinician-worded questions need).
- Fix 5a2 (the AI reads whole passages, not their first 480 characters; G35) tried and dropped
  by its rule: GLM's own catches stayed at 80% (85% needed) and healthy patients left clear fell
  from 3/6 to 1/6.
- With the owner's bigger download pair: fix 5f, search model Qwen3-Embedding-0.6B, passed its
  search check (questions 15/20, ideal 9/12, self-check 32/34, cases 6/12) but failed end to end:
  GLM's own catches fell to 74% (80% needed), healthy left clear 1/6. Dropped. Second time a
  better search score did not bring better catches (5q, 5f), so the end-to-end check decides.
- Laptop setup (2026-11-26): the search model weights live in `D:\Model Weights\huggingface\hub`
  (`ARTEMIS_MODEL_DIR` in `.env`), and the project's PyTorch is the graphics-card build
  (2.15.0+cu132, RTX 3050): the search index builds in 0.6 s instead of 4.3 s (MiniLM), 9.5 s
  instead of about 16 minutes (Qwen3), with the same search results (all 42 searches identical).
  `requirements.txt` keeps the processor build for CI.
- Wrapped up (owner, 2026-11-26) with what is kept: Ugandan guidance only, the AI question step,
  the measuring tools. Fix 5g and 2B.3 not tried: three search changes in a row did not raise
  catches. The owner then decided G33 (a search model that fails to load switches the AI review
  and the plan step off, with a red banner), G36 (citations show the printed page), 2B.7, 2B.6 and
  2B.5 (below). The reviews added G37 (an edited guideline file gets a fresh stored index).
- Final check (3 runs per case, temperature 0): GLM own catches 80%, Llama 55% (59% Uganda-only
  baseline; passes by 1 point), DeepSeek 61% (67% in Phase 2 with all four guidelines at 0.2;
  real alerts 91%, healthy left clear 5/6). Write-up: `eval/phase2b/README.md`; screenshots of
  the banner and the citations in `eval/phase2b/`. Spent $2.00 of the $5 cap in all.
- Open, carried to item 8.5 (records per recommendation): G34 (pieces longer than the search
  model reads) and the rest of G31 (rule-alert searches use the fixed query builder).

- [x] 2B.1 Retrieval check on its own: for each case, does the right guideline passage come back?
      This separates "looked in the wrong place" from "read the right page and reasoned badly".
      Done 2026-11-25: `scripts/check_retrieval.py`, `scripts/diagnose_search.py`.
- [x] 2B.2 Try the simplest fixes first (guideline-structure chunks, keyword plus meaning search,
      a re-ranking step), one at a time, keeping each only if the scores improve. Done: 5a, 5b, 5c,
      5d, 5e, 5a2, 5f tried and dropped by their rules; 5q (AI-written questions) kept.
- [ ] 2B.3 Try an agentic loop like PolicyLens: plan the questions, search, judge whether the
      results are good enough, search again if not. Not tried: the owner wrapped up 2B first
      (2026-11-26); better search did not raise catches twice.
- [x] 2B.4 Pick the winner on the numbers and write up what was learned (a good demo piece too).
      Done: `eval/phase2b/README.md`.
- [x] 2B.5 Decided 2026-11-26 (owner, option B): keep Chroma and keep skipping its four advisories,
      with the reason in `.github/workflows/security-scans.yml`; 1.5.9 is still the newest release and
      the app never starts Chroma's HTTP server. Recheck on every chromadb upgrade. Replacing Chroma
      with the simple saved search (about 27 fewer libraries) stays an option for Phase 4.3.
      The item was: revisit the four accepted chromadb advisories: replace or upgrade Chroma, then remove
      their `--ignore-vuln` lines from `.github/workflows/security-scans.yml`.
- [x] 2B.7 Decided 2026-11-26 (owner, option A): plain text cut into pieces stays, the best setup
      measured end to end; sections (fix 5b) measured worse on questions and patients; one record
      per recommendation becomes Phase 8 item 8.5. Meaning search stays (keyword search, 5c, dropped).
      The question was: how the guideline knowledge is stored, decided on the 2B.1 numbers: plain Markdown as
      today, Markdown split along the guideline's own sections, or structured records (JSON, one per
      recommendation, with drug, condition, action, country and edition). Also which search fits
      each: meaning search, keyword search, or both together, and filters by country and edition.
- [x] 2B.6 Decided 2026-11-26 (owner, option A): the repository keeps only what the app uses, the 2
      Ugandan extracts, with a sources list in `Data/MarkDown Files/README.md`; the 3 PDFs and the
      South African and WHO extracts stay on the owner's computer (`.gitignore`). They remain in the
      repository's history; rewriting it would be a separate decision. The question was: where the guideline files live, once 2B has picked the documents and how their text
      is extracted. The documents are picked: Uganda's only (owner, 2026-11-25); `artemis/guidelines/sources.py`
      is the start of the sources list. Today the app searches the 2 Ugandan Markdown files in `Data/MarkDown Files/`; the 3 PDFs in
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
- [ ] 4.5 Move the visit records from fix 9's local files into Postgres.
- [ ] 4.6 (suggested) Phase 1 code review follow-ups, best done as the API replaces the Streamlit
      shell: move the add-case record building out of app.py into a typed endpoint; validate a
      patient record once when it is loaded (4.1); have the model client return the reply with
      its finish reason instead of setting attributes; keep the screen's session keys in one
      place (today in ui/state.py, app.py and visit_record.restore); share one JSON bracket
      scanner (screening and plan_json); drop unused fields (deterministic_alerts, used_llm).

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
- [ ] 6.3 README rewrite: screen recording, the preliminary results table (marked as such until
      Phase 7), limitations, "not for clinical use".

Check: the live Pages link works in a fresh browser with no VPN.

## Phase 7: Clinical check with the doctor

Everything that needs the doctor, done together once the app is built and running (owner,
2026-11-25).

- [ ] 7.1 The doctor reviews and corrects the draft answer key and adds cases, to about 30
      (Timothy's test cases too, if he takes part).
- [ ] 7.2 Targets for sensitivity, precision and specificity, set with the doctor (owner's working
      figure: about 85%).
- [ ] 7.3 The clinical calls held from Phase 1: whether to flag problems outside HIV-drug safety,
      such as Kintu's blood pressure (G39); whether P002's monitoring reminders and P004's
      "missing labs" alert are false alarms.
- [ ] 7.4 The final run on the clinician-checked answer key: the accuracy table the README reports,
      with the method written up (done criterion 2).
- [ ] 7.5 Clinician trial (was 6.4): the doctor uses the running app on the test cases and reports
      what to improve. Their findings become new cases.
- [ ] 7.6 Before 7.4's run, tidy the evaluation scripts (standards review of Phase 2; the owner
      chose to push Phase 2 first, 2026-11-25): move the run loops, the spending checks and
      "stop when a model call fails" from `scripts/run_phase2.py` and `scripts/run_afrimedqa.py`
      into tested functions in `artemis/evaluation/`, share the helpers copied in two or three
      places, and give the saved run record and quiz answer named types.

Check: the README's accuracy table rests on clinician-checked cases, and `python scripts/evaluate.py`
reproduces it.

## Phase 8: Stretch, as time allows

- [ ] 8.1 CDS Hooks endpoint (patient-view hook, cards, feedback), so record systems such as
      OpenMRS-based UgandaEMR could call it.
- [ ] 8.2 FHIR import (Patient, Condition, MedicationStatement, Observation), tested on Synthea's
      synthetic HIV patients.
- [ ] 8.3 (suggested) Rules-only mode that works with no model connection (winners of the challenge were offline-first).
- [ ] 8.4 (suggested) "Left in red" view: how often critical alerts are left unresolved (Penda's main lever).
- [ ] 8.5 One record per guideline recommendation (medicine, condition, action, printed page),
      drafted by an AI from the Ugandan extracts and checked by the doctor (Phase 7), so the app finds
      rules by medicine name and simple code can check some without the AI (from 2B.7, 2026-11-26).

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
2. Database: Postgres (owner, 2026-11-25), hosted somewhere like Railway or Cloudflare; the host
   is still open. Until then the visit record is a local file (fix 9).
3. Which OpenRouter models, and a spending cap: decided 2026-11-25 (DeepSeek V3.2, GLM 5.2, Claude
   Haiku 5.5; $5). MedGemma-27B left out for now. After Phase 2 the shortlist is locked (owner,
   2026-11-25): GLM 5.2 leads, DeepSeek V3.2 is the runner-up, Llama on the A100 stays as the
   in-house comparison, Claude Haiku 5.5 is dropped. A working pick, not final: Phase 7 decides.
4. Whether Timothy and Dr Kintu write and label the cases, and how they are credited (Phase 7).
5. Where the explainer videos live (YouTube, or small files in the repo).
6. Whether to mirror this checklist as GitHub issues and milestones.
7. Keep or cut the items marked "(suggested)", which were my additions.
8. The target for each of sensitivity, precision and specificity (owner's working figure: about 85%),
   agreed with the doctor in Phase 7.
9. Whether real patient records may be sent to a hosted model (OpenRouter and the company that
   runs the model). Until the owner decides, anything with real data runs on Llama on the A100.
