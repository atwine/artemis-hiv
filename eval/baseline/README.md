# Baseline, 2026-11-25 (plan item 1.0)

The "before" snapshot that every Phase 1 fix is judged against. `scripts/run_baseline.py`
ran all 7 test patients 3 times each through the app's own analysis, at commit `3e75a1e`,
on Llama 3.3 70B (AWQ 4-bit) on the A100, with the app's default settings. `summary.md` is
generated from the JSON files; this file is written by hand.

Labels: **measured** means counted from the saved files; **inferred** means a reading of
them that a clinician should confirm.

## What the runs show

1. **The plan says "AGREE" when the model gave no verdict** (measured, fix 1.2). The plan
   had 44 items across the 21 runs. 36 of them (82%) came back with no verdict on whether
   the clinician's plan covers them, and the screen shows every one of those as "AGREE".
   The other 8 really did say "Agree". The model never answered "Gap" or "Disagree".
2. **The fixed-rule alerts are thrown away** (measured, fix 1.1). The rules flag P001
   (creatinine overdue on TDF) and P003 (creatinine missing on TDF, possible EFV side
   effects). Once the AI screening succeeds, the app drops them. The AI caught the EFV
   effects in 3 of 3 runs and P001's creatinine in 2 of 3. For P003's creatinine it gave
   only a general "Missing Laboratory Results".
3. **Patients expected to be clear still get alerts** (measured). P002 is expected GREEN
   and got 3 to 5 alerts in every run. P004 is expected GREEN and got 2 in every run.
   P002's "Missing Laboratory Results" alert says there are no lab results, but the record
   has a viral load from September 2025 and a creatinine from December 2025 (inferred: a
   false alarm).
4. **Kintu's blood pressure rise is missed** (measured). It went from 118/74 at the TLD
   switch to 138/88 today. None of the 3 runs mentions blood pressure.
5. **Answers change from run to run** (measured). The number of alerts changed between
   runs for 2 of the 7 patients (P002: 5, 3, 3; Kintu: 3, 2, 3), and P004 was RED once
   and YELLOW twice. Titles shift too. So compare before and after across all 3 runs,
   never one run against one run.
6. **A quarter of the guideline passages are South African** (measured, fix 1.4). Of 335
   passages retrieved, 239 (71%) came from the Uganda HIV guidelines, 86 (26%) from the
   Southern African HIV Clinicians Society 2024 guideline, and 10 (3%) from WHO. Citations
   on screen don't say which country a passage comes from.
7. **Speed** (measured). The median was 46.5 s per run, with a range of 31.8 to 286.3 s.
   The slowest was the first run, which included loading the search index.

There were no model errors, and every screening reply parsed.

## Rerunning after a fix

```bash
python scripts/run_baseline.py --out eval/after-1.1
```

Compare the new `summary.md` with this folder's. The A100 needs eduVPN.
