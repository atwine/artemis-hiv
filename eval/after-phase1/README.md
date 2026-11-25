# After Phase 1, 2026-11-25 (plan item 1.Z)

The same run as `eval/baseline`, repeated after Phase 1's ten fixes: `scripts/run_baseline.py`
ran all 7 test patients 3 times each through the app's own analysis, on Llama 3.3 70B (AWQ
4-bit) on the A100, with the same settings (the agentic plan switched on). The code was commit
`a6fc3f9` plus the baseline script's own repair (it had broken when Phase 1 moved code; see
`eval/fixes/phase1-review-findings.txt`). The review fixes committed afterwards (`fd98185`)
don't change what the AI review finds. `summary.md` and `compare.md` are generated; this file
is written by hand.

Labels: **measured** means counted from the saved files; **inferred** means a reading of them
that a clinician should confirm. Answers vary between runs, so every comparison uses all 3.

## What changed, against the baseline's findings

1. **No plan item shows a made-up "AGREE"** (measured, fix 7). Before, 36 of 44 plan items had
   no verdict and were shown as "AGREE". Now all 52 items have one: 47 Not Addressed, 3 Gap,
   1 Disagree, 1 Agree. Every plan passed the app's own checks (17 of 21 failed before).
2. **Rule alerts are shown, and the rules see more** (measured, fixes 3 and 5). Before, P001's
   and P003's rule alerts were dropped whenever the AI review worked, and P005, P006 and Kintu
   got no rule alerts because their regimen was written as a sentence. Now every rule alert
   is shown: P001 1, P003 2, P005 3, P006 1, Kintu 1, in all 3 runs.
3. **Far fewer "missing data" false alarms** (measured, fixes 4 and 6). Alerts claiming
   missing labs, history or plan, across the 3 runs: P002 5 before, 0 after; P003 5 to 0;
   P004 3 to 1; P001 1 to 0; Kintu "Missing Monitoring Data" 2 to 0. The remaining one, P004's
   "Missing Lab Results" in run 3, is still wrong: P004 has a viral load and a creatinine from
   2025-11-05 (inferred: a model judgement miss, Phase 2).
   New: "Missing Assessment and Plan" for Kintu (2 runs) and P005 (1 run). Both records have
   an empty assessment and plan for today, so these are true (measured: the note is empty).
4. **Kintu's blood pressure rise is noticed** (measured). Before: 0 of 3 runs mentioned blood
   pressure. After: 2 of 3 ("Blood Pressure Elevation"). The likely reason is fix 6, which put
   today's examination findings into the summary the AI reads (inferred). One run still
   misses it, so this stays a Phase 2 measurement.
5. **The patients expected to be clear are still YELLOW** (measured). P002 gets two low
   "Viral Load Monitoring" and "Creatinine Monitoring" alerts in every run, although its last
   viral load was 129 days and its creatinine 38 days before the visit (inferred: false
   alarms of judgement, not of missing data). P004 gets "Abdominal Pain" in every run, which
   matches its note. Both go to Phase 2, where accuracy is measured against labelled cases.
6. **The AI's references are what it was shown** (measured, fix 8). 46 of 49 AI citations
   point to passages the AI was shown; the other 3 are marked on screen. An AI alert now lists
   only those, so far fewer passages per alert are listed than the baseline's fresh searches.
7. **Every AI reply was read in full** (measured, fix 8). 21 of 21 screening replies parsed
   completely; no model errors.
8. **Faster** (measured). Median time per run 18 to 33 s, against 34 to 59 s before, mostly
   because fix 7 removed the plan's never-shown verification call.
9. **Still varies between runs** (measured). Kintu's AI alerts were 2, 5, 5 and once RED; P003's
   1, 2, 2; P005's 5, 3, 3. Phase 2 judges each case over several runs (G38).

## What this run can't show

- The screen-only fixes (fix 2 results tied to the patient, fix 9 visit record, fix 10 labels
  and hidden server address) were checked with screen tests and in Chrome; see
  `eval/fixes/fix2-*`, `fix9-*` and `fix10-*`.
- How the cleaner fix (fix 10) changes what the AI is shown is measured in
  `eval/fixes/fix10-after.txt`: 23 thresholds such as "<50" in the passages shown, against 9.

## Rerunning

```bash
python scripts/run_baseline.py --out eval/<folder>
python scripts/compare_runs.py eval/baseline eval/<folder> > eval/<folder>/compare.md
```

The A100 needs eduVPN.
