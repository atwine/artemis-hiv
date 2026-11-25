# Lessons learned: silent failures in AI-assisted clinical code

ARTEMIS-HIV was first built quickly, with AI coding help and a small 4B model, for a
competition. Phase 1 of its revival read every function and tested the app against real test
patients. Almost nothing crashed. The faults below gave wrong answers quietly, which is the
dangerous kind in clinical software.

Each entry has the pattern, a real example from this app, how it was caught, and the fix. New
entries are added at the end of each fix (see `docs/refactor/README.md`).

## Patterns

**1. A missing answer shown as agreement.**
- Example: the management plan showed "AGREE: matches your plan" whenever the model gave no
  verdict. 36 of 44 plan items had no verdict. For 3 patients the clinician had written no plan
  at all, and the screen still said "Matches your plan".
- Caught by: the baseline run saved the model's raw verdict next to what the screen showed.
- Fix: Phase 1 fix 7 (planned).

**2. A failure that looks like success.**
- Example: when the AI's reply couldn't be read, or the server didn't answer, a patient with no
  rule alerts was shown as GREEN. The banner said the AI review "was not executed", although it
  had run, and Finalize opened with nothing reviewed.
- Caught by: feeding the analysis stand-in replies (unreadable text, a server error) and
  checking the result.
- Fix: fix 3. Each run now records one outcome (ok, failed, unreadable or not run), and a failed
  review shows an amber "AI review failed" banner and is never green.

**3. A later step silently replaces an earlier one.**
- Example: the fixed safety rules flagged John's overdue creatinine on tenofovir. As soon as the
  AI replied, its alerts replaced the rule alerts. In one baseline run the AI didn't mention
  creatinine, so the warning vanished. When the AI found nothing, John showed GREEN.
- Caught by: the baseline saved the rule alerts separately from what the screen showed.
- Fix: fix 3. Rule alerts always show, tagged "Rule check", next to "AI review" alerts.

**4. Results not tied to the person they belong to.**
- Example: after saving John's visit and switching to Jane without saving, the screen showed
  John's creatinine alert under Jane's name, and Jane's visit could be finalized on John's
  reviews.
- Caught by: driving the real screen headlessly (Streamlit's test runner), switching patients
  and reading what's on screen.
- Fix: fix 2. Each result records its patient and note, and switching patients clears it.

**5. The model is given contradictory input.**
- Example: the screening prompt said "Laboratory results: None recorded" whenever the free-text
  lab box was empty. The structured summary further down the same prompt listed a viral load
  from September and a creatinine from December. The model raised "Missing Laboratory Results"
  for stable patients in all 12 of their runs.
- Caught by: rebuilding the exact prompt the model received, with a stand-in model that
  records its input.
- Fix: fix 4. The model now reads a dated table of every result, with its unit and age in days,
  and notes labelled with their dates (fix 6 handles the false "missing" flags in the summary).

**6. Guideline text damaged before the model reads it.**
- Example: a cleaner meant to strip HTML tags deleted everything between "<" and ">". So
  "VL < 50 … CD4 > 200" lost its numbers: 49 thresholds in all, and 5.8% of one guideline. A
  chart now read as if a viral load of 50 needs enhanced adherence support.
- Caught by: the audit compared the cleaned text with the original files.
- Fix: Phase 1 fix 10 (planned, pulled forward from the retrieval revamp).

**7. Copies that drift apart.**
- Example: the form's reset list named fields that no longer existed, so the next patient's form
  kept the previous patient's lab results. The plan display existed twice, and one switched-off
  copy still carried the "AGREE" fault.
- Caught by: the audit read every function, including code that never runs.
- Fix: fixes 1 and 2. The dead copies were deleted, and the form now clears every field whose
  name starts with its prefix.

**8. Code written for an older model, kept for a newer one.**
- Example: clean-up steps built to tame a small 4B model's repetition merged look-alike alerts.
  With the 70B model they dropped a real hepatitis B alert, merged a viral-load alert into a
  creatinine one, and cut "Hb 9.1 then 7.2" to "Hb 9.1".
- Caught by: replaying the baseline's real model replies through the clean-up code.
- Fix: Phase 1 fix 8 (planned).

**9. A test that blesses the bug.**
- Example: the first "golden" test recorded the app's output as correct, including the dropped
  rule alerts. It would have failed the fix, not the fault.
- Caught by: the audit read the tests as well as the code.
- Fix: every time the golden output is rewritten, the commit lists exactly what changed for each
  patient (fix 3: John and P003 gained their rule alerts, and nothing else changed).

**10. A test that writes to real data.**
- Example: the first run of the add-patient test saved a test patient into the real patient
  list, because the app had no way to point it elsewhere.
- Caught by: `git status` after the run showed the data file had changed. The file was restored
  from git.
- Fix: fix 2. The patient file's location can be overridden, and the tests use a temporary copy.

**11. Slow work hidden by caching.**
- Example: on every start the app re-read and re-embedded all four guideline files (about 880
  passages), although the index on disk already held them. The first Save took 3 to 4 minutes,
  even with the AI off.
- Caught by: timing a Save on the code before and after a fix, to rule out the fix as the cause.
- Fix: plan item 4.3 (keep the index), and how the index is built in the retrieval revamp.

## Habits that caught these

- Save a baseline before fixing anything, including the model's raw replies and the rule alerts,
  not only what the screen shows.
- Rebuild exactly what the model was given, using a stand-in model that records its input.
- Drive the real screen headlessly and read what a clinician would see.
- Write the test first, watch it fail for the predicted reason, then fix.
- Have a second reviewer rerun every serious finding before it counts. All 48 held up.
- When an expected output is rewritten on purpose, list what changed for each patient.

**12. Units carried in a field's name, then dropped.**
- Example: lab values were saved under keys like `value_umol_per_l`, so the unit lived only in
  the key name. The summary kept just the number, and the model saw "creatinine 76" with no unit.
  The add-patient form saved any creatinine as umol/L, so 1.4 (mg/dL) became 1.4 umol/L, a
  90-fold error.
- Caught by: the audit followed one value from the form to the model's input.
- Fix: fix 4. Each result stores its unit next to its value. The form asks for the unit, and
  refuses a creatinine under 20 umol/L as probably mg/dL.

