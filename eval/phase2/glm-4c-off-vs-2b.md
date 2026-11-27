# GLM 5.2 on today's code against GLM's Phase 2B run (2026-11-27)

`runs/glm-5.2-t0-4c-off` is GLM 5.2 on OpenRouter, thinking off, temperature 0, through the
backend (11 cases, 1 run each). Today's code has the plan reading the patient's labs, the
Uncertain flag, the two reworded fixed rules and the stricter key. `runs/glm-5.2-t0-5q` is GLM's
Phase 2B final run (3 runs a case), made before those changes. Both are scored with the stricter
key. Its fixed-rule alerts are counted with today's wording, as the Phase 4 check accepts it
(`eval/phase4/rule-wording-accepted.txt`); the AI's own alerts are as saved.

This run started as the "thinking off" half of a thinking on/off experiment. The thinking-on
half failed on its first visit: GLM spent each call's whole reply room on thinking and gave no
alert list. The owner stopped the experiment there ("let's not continue with thinking turned on")
and turned thinking off by default (`docs/decisions.tsv`, 2026-11-27).

**One run against three.** Each case ran once today, so one changed run moves a case's result.
Read differences of one or two as noise unless they repeat.

| | Today, `4c-off` (1 run) | 2B, `5q` (3 runs) |
|---|---|---|
| Problems caught by the AI | 73% (16/22) | 79% (52/66) |
| Problems caught, fixed rules included | 82% (18/22) | 82% (54/66) |
| Alerts that are real problems | 89% (41/46) | 88% (120/136) |
| Healthy patients left clear | 0/2 | 3/6 |
| Runs breaking a must-not | 2/10 | 6/30 |
| Plans flagged Uncertain (ART decision) | 2/11 (P003, P005) | not flagged then; 1 of the 3 P005 plans said Uncertain |
| Plans that failed their checks | 0/11 | 3/33 |
| Visits whose plan was asked again (cut off or unreadable) | 5/11 (6 extra calls) | 4/33 (7 extra calls) |
| Alert lists cut off at their limit | 1/11 (Kintu-Test 001, 4 AI alerts kept) | 0/33 |
| Cost per visit | $0.011 (range $0.005 to $0.022) | $0.009 (range $0.005 to $0.024) |
| Cost per 100 visits | $1.09 (range $0.51 to $2.22) | $0.93 (range $0.47 to $2.43) |
| Seconds per visit, median | 147 (range 136 to 241) | 21 (range 12 to 48) |
| Total spent | $0.12 | $0.31 |

All measured, from the saved runs, except where marked below. The per-100 ranges are each run's
cheapest and dearest visit times 100.

## What's new

- **Rose Nabirye's plan (P005) now sees her labs.** In 2B the plan step had no lab values: its
  plans spoke of "no labs available" and "no labs are recorded", and two of the three kept her
  regimen ("Continue"; the third said Uncertain). Today's plan
  names the creatinine rise from 0.9 to 1.4, the eGFR of 52 and the protein and glucose in her
  urine, and says TDF may need switching to ABC. It still marks the ART decision **Uncertain**,
  because "the guideline excerpts do not contain specific TDF toxicity management", and the app
  shows the Uncertain flag. The guideline does give the action (HIV Guidelines 2022 p. 270:
  substitute TDF with ABC when the GFR is below 60). So the plan step didn't get that passage
  from the search (inferred; the run doesn't save the plan's passages). That's the search work
  in PLAN.md 8.5, not a plan bug.
- **Ibuprofen with TDF.** Today's plan for Rose doesn't list ibuprofen as a problem. All three 2B
  plans did, with "counsel on limiting ibuprofen" or "reduce ibuprofen". The AI's kidney alert
  says "address concurrent ibuprofen use" but has no separate ibuprofen alert, so the AI missed
  `nsaid_with_tdf` this run (2B caught it in 2 of 3). The reworded fixed rule caught it: stop or
  avoid the NSAID, paracetamol instead, check kidney function.
- **The AI caught a little less** (73% against 79%). The misses: P005 ibuprofen (above), and
  P003's "creatinine never done" (2B caught it in 2 of 3). Everything else the AI caught matches
  what 2B caught in every run. With one run, this may be noise.
- **Both healthy patients got one extra alert.** P002: "TDF renal monitoring may be overdue".
  P004: "Low-level viremia at 25 copies/mL", advising reassurance and routine monitoring.
  2B left P004 clear in all 3 runs and P002 in none.
- **Must-nots.** EX2 broke `switches_tdf_permanently` with an alert offering to "substitute TDF
  with an alternative agent... or" interrupt it for a while. EX3 broke `switches_dtg` with "reassess
  weight before switching DTG... then consider DTG substitution". Both are conditional advice the
  key reads as a switch; worth the doctor's look in Phase 7 (`eval/cases/KEY-CHANGES.md`).
- **Slower: 147 seconds a visit against 21**, for about the same number of tokens (75k in and 25k
  out over 11 visits, against 199k and 61k over 33). OpenRouter sent the calls to slower
  providers today (inferred). The saved usage doesn't say which provider served a call, and
  OpenRouter lists about 30 for GLM 5.2, priced $0.45 to $2.31 per million tokens in and $1.44 to
  $8.00 out (measured from its public list, 2026-11-27). Speed and cost will vary until a
  provider is chosen in the request.

## Thinking on, for the record

Not run; nothing saved. EX2 was re-run once with each call shown. The search questions used
300 of 300 tokens thinking (empty answer); the alert list 1,600 of 1,600 (empty, so the visit
failed); the plan 932 of 1,000 (258 characters, cut off); the plan retry 1,000 of 1,000 (empty).
The failed visit and that re-run cost about $0.025, which no saved run records (measured for
the re-run, inferred for the failed visit), so `spent_in` reads that much low.
