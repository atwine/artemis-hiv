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
- Fix: fix 7. The screen shows only what the AI said: "Not assessed" when there's no verdict, "No
  plan to compare" when the clinician wrote none, and a grey "Needs review" for an unclear
  decision.

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
- Again in fix 10: a check script called the app directly and would have saved its visits into
  the real visit records. It was stopped before any line was written. The test suite, the
  baseline script and the check scripts now send records to throwaway folders themselves.

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

**13. Exact-match rules on free text.**
- Example: the rules checked for the exact entry "TDF" in the regimen list. P005's regimen was
  saved as one sentence ("TDF/3TC/DTG (TLD) fixed-dose combination once daily…"), so she got no
  rule alerts at all: not for tenofovir with ibuprofen, not for her kidney function, not for
  protein in her urine. "TDF, 3TC, EFV" typed normally failed too, because of the spaces after
  the commas.
- Caught by: running the rules on every saved case, not only the four tidy demo patients.
- Fix: fix 5. One function recognises the drugs however they're written, the form uses a
  pick-list, and the old cases were converted once with their original text kept.

**14. "Found nothing" reported as "missing".**
- Example: the summary flagged a field as missing whenever a keyword search found nothing. Today's
  plan counted only on lines starting "Plan:", and other medicines were read from a field name no
  record had. So all 7 patients were told "today's plan: missing" and "other medications:
  missing", and the AI raised "No Current Clinician Plan" and "Incomplete Medication History"
  for patients whose records had both.
- Caught by: printing the summary for every patient next to their actual record.
- Fix: fix 6. The summary carries the recorded values themselves, and lists a field as not
  recorded only when it is truly empty.

**15. The model's instructions and the app's check contradict each other.**
- Example: the plan prompt told the AI to include a verdict "ONLY if the clinician plan differs
  or is missing". The app's validity check required a verdict on every item. So 17 of 21 plans
  failed the check, were retried twice, and were then shown anyway with no warning. The prompt
  also invited "Uncertain: …" answers that the check rejected and the screen drew as a green
  "Continue".
- Caught by: replaying the saved plans through the check, and reading the prompt and the check
  side by side.
- Fix: fix 7. One shared check, a prompt that asks for what the check requires, and plans that
  still fail are marked as failed on screen.


**16. "Couldn't read it" reported as "found nothing".**
- Example: the reply reader took the first "[" in the text. A reply that began "Based on the
  guideline excerpts [1], these are the alerts:" and then listed 3 alerts came back as an empty
  list, which the app reads as "the AI found no issues". A list of plain sentences did the
  same. A reply cut off part-way lost every alert, including the complete ones before the cut.
- Caught by: feeding the reader stub replies in each shape a model can produce, and checking
  the status it reported, not only the alerts.
- Fix: fix 8. The reader looks past bracketed words, accepts a single alert, keeps the complete
  alerts from a cut-off reply, and says which happened. A cut-off or partly read reply gets an
  amber banner and is never green.
- The same pattern in the saved cases file (fix 10): any read error made the file count as
  empty, so one bad character meant the next added case overwrote every saved case. A file
  that can't be read is now reported, and nothing is written to it.

**17. A clean-up written for one model, kept for the next.**
- Example: the 4B model repeated itself, so a cleaner merged alerts whose titles were 75% alike
  and deleted sentences that were 75% alike. With the 70B model it did harm: "Missing hepatitis
  B test" was dropped as a copy of "Missing creatinine test", a high viral-load alert was merged
  into a moderate creatinine one, and "Hb was 9.1 g/dL in January. Hb was 7.2 g/dL in March."
  became "Hb was 9.1 g/dL in January.", hiding the fall.
- Caught by: running pairs of different alerts through the cleaner and counting what came out.
- Fix: fix 8. The cleaner is deleted. Only exact repeats are dropped, and alerts with the same
  id are kept apart.

**18. Evidence the AI never saw, shown as its sources.**
- Example: after screening, the app ran a fresh search for each alert and listed those passages
  as the alert's References, merged with the pages the AI cited. 273 of the 335 listed passages
  in the baseline were never shown to the AI. The AI could also cite a passage it was never
  given, and nothing checked.
- Caught by: comparing each alert's listed passages with the passages actually sent to the AI.
- Fix: fix 8. An AI alert lists only the passages it was shown and cited. A citation to anything
  else is kept but marked "not among the passages the AI was given". A rule alert's passages are
  labelled as search results.

**19. A success message for work that never happened.**
- Example: Finalize showed "Visit finalized." but only set a flag in the screen's memory. The
  reviews, the override reasons and the note were never written anywhere, and a page reload
  lost them all. An override with reason "Other" and no comment also passed.
- Caught by: driving the real screen headlessly, pressing Finalize, and listing the files that
  changed on disk (none).
- Fix: fix 9. Each run of the checks and each Finalize adds a line to the patient's record file.
  The screen says "finalized and saved" only after the line is written, and says so when saving
  fails. "Other" needs a comment.
- Related (fix 10): labels written ahead of time. Every alert's details said "LLM unavailable"
  even when the AI had run, the status named a step that no longer existed ("generating audit
  checklist"), and every patient showed "Visit Type: Routine". Labels now come from what ran
  or what is recorded.

**20. A cleaner that deletes what it doesn't recognise.**
- Example: the guideline text cleaner removed anything between "<" and ">" as if it were an HTML
  tag, so "If VL < 50 copies/mL and CD4 > 200, continue." became "If VL  200, continue." It also
  dropped every "figure" block, one of which held a WHO 2025 treatment recommendation. Across the
  four guideline files it kept 289 thresholds like "<50"; the fixed cleaner keeps 540.
- Caught by: feeding the cleaner one real guideline sentence and reading what came out.
- Fix: fix 10. It removes only named HTML tags, keeps the text of figure blocks, and the
  guideline index is rebuilt.

**21. A backup that quietly holds less.**
- Example: when the guideline database can't open, the app falls back to an in-memory copy. That
  copy replaced its contents with each file it was given, so only the last guideline file could be
  searched, while indexing reported every passage as done.
- Caught by: reading how the indexing loop and the backup store fit together, then indexing two
  files and searching for the first.
- Fix: fix 10. The backup adds each file's passages. Whether the app should also warn when it
  falls back is a Phase 2B question.

**22. A label more confident than the numbers.**
- Example: lab "trends" were labelled by counting ups and downs. Creatinine 70, 150, 140, 130 was
  "FALLING" although it nearly doubled; two undetectable viral loads (30, then 20) were "FALLING";
  "<50" was dropped as not a number; and a pasted lab paragraph was labelled as a trend. The AI
  plan step read these labels.
- Caught by: printing the label next to the values for every patient.
- Fix: fix 10 (owner's pick). The labels are gone; the AI reads the dated values themselves, and
  trend rules come back when the doctor sets them.

**23. Scripts nobody runs break quietly.**
- Example: Phase 1 moved code out of app.py. The tests passed, but the baseline script still
  called app.run_alerts and crashed on its first patient, and the old demo script still passed a
  removed argument. Neither ran in the test suite, so nothing noticed until the script was used.
- Caught by: the end-of-phase rerun itself, and a review that read the scripts outside the diff.
- Fix: 1.Z. A test now runs the baseline script on one patient, and another checks the demo's
  call against the function it calls.

**24. A reply format fixes what an instruction can't.**
- Example: the prompt told the model to leave citations empty when no passage supported an
  alert, yet Llama kept citing a made-up "information_gap" passage: 12 of its 144 citations named
  nothing it had been shown. In the AfriMed-QA quiz, "reply with only the option key" got a
  sentence from Claude 1 time in 3.
- Caught by: counting citations against the passages each run was shown, and reading the quiz
  replies that could not be scored.
- Fix: Phase 2, steps 6 and 8. The reply format lists the allowed values (the ids of the passages
  shown; the question's own option keys), so a server that follows the format can't produce
  anything else. Citations to passages shown went from 92% to 100%.

**25. A reply limit sized for one model cuts off another.**
- Example: the app allows 1,600 tokens for the alert list and 1,000 for the plan, set when Llama
  was the only model; its longest reply in 110 checks was 769. Claude Sonnet 5.5 can't switch
  its thinking off and spent 877 tokens thinking, so its alert list was cut off. Claude Sonnet 5
  with thinking off filled all 1,600 too.
- Caught by: one trial check per model before the paid runs, reading the finish reason and the
  token counts of every call, not only whether alerts came back.
- Fix: Phase 2 used models that fit (owner's pick). The limits go on the rebuild list.

**26. Word rules reward long answers.**
- Example: Phase 2 matched alerts to the answer key by words in the whole alert. GLM's alerts ran
  a median 96 words, Llama's 40. On the dehydration case, long alerts tripped "blames TDF" by
  quoting the guideline's condition ("if renal impairment develops due to TDF") while saying the
  cause was dehydration. The same length earns extra credit when counting catches.
- Caught by: reading every "must not" hit in context before reporting the count.
- Fix: the write-up gives the word-rule count beside a hand reading. The doctor's check of the
  matches in Phase 7 replaces both.

**27. Numbers typed into a write-up drift from the data.**
- Example: the Phase 2 write-up said 12 of 22 problems were caught every time by every model,
  naming EX3's thyroid among them; the saved runs give 10, and DeepSeek caught the thyroid in 4
  of 5. "1 catch in 25 runs" counted Llama twice (both temperatures). The counts came from a
  scratch script that nothing kept, and the shared rule alerts quietly lifted every model's
  catch rate.
- Caught by: the spec review, which rebuilt every number from the saved runs.
- Fix: the results script now prints the count for every problem, the AI's own catches
  without the rule alerts, and the plan cut-offs, so each number in the write-up can be
  checked against generated output.

**28. A folder rule decides what the AI reads.**
- Example: the app searched every Markdown file in its guideline folder. The South African and
  WHO guidelines sat there beside the Ugandan ones, so 54% of the passages the AI read for
  Ugandan patients were South African, and the search database still held 1,323 non-Ugandan
  pieces in two old collections. Nobody chose that; it followed from "take every file".
- Caught by: the search check, which lists the guideline each returned passage came from, and
  the owner asking whether foreign documents were in the database.
- Fix: Phase 2B. A register of approved guidelines with their country; the app loads only
  Uganda's, the other files moved out of the folder, the database deleted and rebuilt, and
  `scripts/check_index_sources.py` fails if any non-Ugandan piece is in it. Standalone questions
  answered in the top 5 went from 3 of 20 to 13 of 20.

**29. A better search score is not a better app.**
- Example: the Qwen3 search model found the right guideline passage far more often (questions
  15/20 against 13/20; answer-key summaries 9/12 against 6/12), yet with it the AI caught fewer
  problems (74% against 80%) and raised alerts on more healthy patients (1 of 6 left clear
  against 3 of 6). The AI-written questions (5q) also found more passages with catches unchanged.
- Caught by: each fix's keep rule had two parts, the search check and then the whole app end to
  end, written before the run. Judged on the search check alone, Qwen3 would have been kept.
- Fix: Phase 2B keeps the end-to-end check as the deciding one, and the write-up
  (`eval/phase2b/README.md`) says so.

**30. A page number has to be the book's page.**
- Example: citations said "p.22", the 22nd page of our extract file; the rule is on printed page
  255 of the guideline. A clinician turning to page 22 would find something else.
- Caught by: the Phase 1 audit (G36), confirmed by matching extract pages to the PDF.
- Fix: Phase 2B reads each extract page's printed number and refuses a file whose numbers do not
  run in order; citations now read "Uganda HIV guidelines 2022, p.255".
