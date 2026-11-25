# Phase 2: a first evaluation without the doctor (2026-11-25)

Preliminary numbers on how well the app finds the problems in an HIV clinic visit, and a first
comparison of models. No clinician has checked the answer key yet; that is Phase 7. These
numbers steer the work. They are not the app's accuracy and should not be quoted as such.

Labels: **measured** means counted from the saved files; **inferred** means a reading of them.

## What was tested

**Cases.** 11 visits in `eval/cases/`, each a frozen patient record in the app's own shape,
with the clinician's note, plus an answer key:

| Case | Where it comes from | Expected problems | Must not say |
|---|---|---|---|
| P001 | test patient | creatinine overdue on TDF | |
| P002 | test patient | none (should stay clear) | labs missing; no plan |
| P003 | test patient | efavirenz side effects; creatinine never done | no plan |
| P004 | test patient | none (should stay clear) | labs missing |
| P005 | test patient (also clinician example 1) | kidney harm from TDF; ibuprofen with TDF; viral load before switching | keep TDF |
| P006 | test patient | iron taken with dolutegravir; creatinine rise | avoid dolutegravir in pregnancy |
| Kintu-Test 001 | test patient | weight gain; glucose; lipids on TLD | switch off dolutegravir |
| EX2 | clinician example 2 | kidney injury from dehydration; hold then restart; electrolytes | blame TDF; stop TDF for good |
| EX3 | clinician example 3 | under-treated thyroid; amitriptyline weight gain | switch off dolutegravir |
| EX4 | clinician example 4 | carbamazepine lowers dolutegravir; carbamazepine toxicity; low sodium; repeat viral load | blame adherence |
| MR-KS | Mr K.S. use case | TDF kidney and bone harm; NSAID with TDF | |

Each expected problem names its kind (drug harm, clash, missed monitoring, plan gap). 13 of the
22 also name the guideline passage they rest on (the Uganda HIV guidelines in the app, or SAHCS
guidance). The other 9, mostly from the clinician examples, rest on the clinician's written
answer and have no passage yet; Phase 7 adds them. Some cases also list
"also fine" items: real problems a careful clinician might raise that are not required, such
as Kintu's blood pressure. An alert on one of those is neither credited nor counted as extra.

**Scoring.** An alert catches an expected problem when its text (title, message and
recommended action) contains a word from every group of that problem's word rule. "Must not"
phrases count only when not negated ("do not switch from DTG" is fine). Per model:

- *Problems caught*: expected problems caught, over all expected problems in all runs.
- *Alerts that were real*: alerts that matched an expected or also-fine problem, over all alerts.
- *Clear cases left clear*: runs of P002 and P004 with no extra alert.
- *Must-not broken*: runs that said a must-not phrase, over runs of cases that have one.
- *Same answer across runs*: share of runs matching the most common result for their case.
- *Citations to passages shown*, *replies read in full*, *median seconds*, *cost*: need no key.

`matches.md` lists every alert and what it matched, so the word rules can be checked by eye.

**Runs.** Each case 5 times per model through the app's own analysis (`run_visit_analysis`,
rules plus AI review plus plan step), at the app's temperature (0.2). Llama also ran 5 times
at temperature 0, to see whether a fixed temperature makes the answers repeat (Phase 1 item
G38). The AI plan is saved in each run but not scored.

**Models.** Llama 3.3 70B (4-bit) on the A100 is the baseline. DeepSeek V3.2, GLM 5.2 and
Claude Haiku 5.5 ran through OpenRouter with thinking switched off. Claude Sonnet 5.5 was
dropped after a trial (measured, on P005): its thinking can't be switched off, it thought for
877 tokens, its alert reply was cut off at the app's 1,600-token limit, and the check cost
$0.07. GLM 5.3 also refuses to switch thinking off. Its 15 quiz answers are kept in
`dropped/`.

**AfriMed-QA.** A separate knowledge check: the 286 multiple-choice questions in AfriMed-QA
v2 (Hugging Face `intronhealth/afrimedqa_v2`) that are infectious disease (215) or mention HIV
(90; 19 are both). Each prompt says how many options to pick, and the reply format allows only
that many of the question's own option keys. Temperature 0. A question is right when the model
names exactly the correct keys. This tests what a model knows, not the app's job. The data
file is not in the repo (`eval/afrimedqa/data/` is gitignored); `afrimedqa/*.jsonl` holds only
question ids, answers and costs. The dataset card gives CC-BY-SA 4.0.

## Results

330 visit checks (55 per model, 165 for Llama's three sets) and 1,144 quiz answers, all saved
here. `results.md` is the generated table; the numbers below come from it and from the saved
runs.

### The app's job: 11 cases, 5 runs each

| Model | Problems caught (app: rules + AI) | Caught by the AI's own alerts | Alerts that were real | Healthy patients left clear | Must-not broken: word rules / my reading | Same answer across runs | Median seconds | Cost per check |
|---|---|---|---|---|---|---|---|---|
| Llama 3.3 70B (A100) | 80% (88/110) | 68% (75/110) | 81% (175/216) | 0/10 | 6/45 / 6/45 | 85% | 26 | free |
| DeepSeek V3.2 | 77% (85/110) | 67% (74/110) | 96% (176/184) | 10/10 | 7/45 / 0/45 | 76% | 28 | $0.0011 |
| GLM 5.2 | 86% (95/110) | 84% (92/110) | 92% (194/212) | 8/10 | 8/45 / 0/45 | 82% | 14 | $0.0075 |
| Claude Haiku 5.5 | 82% (90/110) | 75% (83/110) | 94% (152/162) | 5/10 | 9/45 / 4/45 | 82% | 24 | $0.0032 |

Every model cited only guideline passages it was shown (100%). Every alert reply was read in
full except 3 of Haiku's 55. The plan reply is longer: Haiku's was cut off in 24 of 55 runs and
GLM's in 2; Llama's and DeepSeek's never (measured). The plan isn't scored, but a cut-off plan
means a shorter or missing plan on screen.

1. **Every model catches the core problems** (measured). 10 of the 22 expected problems were
   caught in all 5 runs by every model: TDF kidney harm and NSAIDs with TDF (P005, MR-KS),
   efavirenz side effects, overdue and missing creatinine, carbamazepine lowering
   dolutegravir and its toxicity, the repeat viral load in EX4, and EX2's dehydration. The
   differences come from a few problems. Llama found EX4's low sodium in 1 of 5 runs; the
   others in 5 of 5. Haiku never flagged P006's creatinine rise (0 of 5). Only DeepSeek and
   Haiku raised EX2's potassium and sodium. Across the four models, the viral load before a
   switch in P005 was caught in 1 of 20 runs and amitriptyline's part in EX3's weight gain in
   2 of 20. Those two may ask for more than the guideline passages say (inferred); the doctor
   decides in Phase 7. `results.md` has the count for every problem.
2. **Part of every model's score comes from the fixed rules** (measured). The app's rule
   alerts are the same whichever model runs, and they caught some problems for every model
   (P001's overdue creatinine, P003's missing creatinine). Counting only the AI's own alerts
   separates the models more: GLM 84%, Haiku 75%, Llama 68%, DeepSeek 67%.
3. **Llama's weakness is false alarms** (measured). It never left either healthy patient
   clear in 10 runs, and raised 41 extra alerts against DeepSeek's 8, Haiku's 10 and GLM's
   18. Its extras repeat: "Missing Recent Lab Results" on P004, which has recent labs (5 of 5
   runs), and "Viral Load Monitoring" and "Creatinine Monitoring" on P002, which has both.
4. **The word rules misread "must not" on long alerts** (measured, then read by hand). On
   EX2 (kidney injury from dehydration, not TDF), DeepSeek, GLM and Haiku tripped "blames TDF"
   in every run, mostly by quoting the guideline's condition ("if renal impairment develops
   due to TDF, switch to ABC") while saying the cause is dehydration. On EX3 they quoted the
   clinician's plan to switch dolutegravir in order to argue against it. My reading counts
   only these as real (inferred, for the doctor to check): Llama's 5 "labs missing" on P004
   and one "consider switching from DTG" on EX3; Haiku's 3 EX2 runs that lean towards
   switching TDF for good, and one "continue TLD" on P005.
5. **Word rules also favour long alerts when counting catches** (inferred). Median words per
   alert: Llama 40, DeepSeek 70, Haiku 88, GLM 96 (measured). A longer alert contains more
   words, so it matches more rules. GLM's and Haiku's catch rates may be flattered, and
   Llama's short alerts under-credited, until a person checks the matches.
6. **The citation fix worked** (measured). Before it (step 6), 92% of Llama's citations
   (132/144) named a passage it had been shown; after it, 100% for every model.
7. **Temperature 0 makes Llama repeat itself** (measured, Phase 1 item G38). Same answer
   across runs went from 85% to 98%, with no real change elsewhere (78% caught against 80%,
   82% real alerts against 81%).

### AfriMed-QA knowledge check: 286 questions each

| Model | All questions | HIV-related (90) | Infectious disease (215) | Cost |
|---|---|---|---|---|
| Llama 3.3 70B | 77% (219) | 76% (68) | 77% (165) | free |
| DeepSeek V3.2 | 77% (220) | 73% (66) | 78% (167) | $0.01 |
| GLM 5.2 | 81% (233) | 79% (71) | 82% (176) | $0.04 |
| Claude Haiku 5.5 | 76% (217) | 73% (66) | 76% (164) | $0.01 |

GLM got more questions right than the others on the same questions. Counting only questions
where one model was right and the other wrong, GLM beat Llama 26 to 12 (exact test p = 0.03)
and Haiku 27 to 11 (p = 0.01). Against DeepSeek, 28 to 15 (p = 0.07) could be chance. 29
questions were missed by every model; two checked by eye had doubtful crowdsourced answer
keys, so some of the 29 may be key errors (inferred).

### Cost

Recorded in the saved runs: $0.72. OpenRouter's account total: $0.93, the difference being
trial calls while choosing models (measured). The cap was $5.

The runner's worst-case estimate first came from one Llama check (3,940 tokens in, 1,153 out).
The hosted models made up to 4 calls a check, so their real cost ran up to 3 to 4 times that
estimate (measured: Haiku $0.0040 against $0.0012, GLM $0.0156 against $0.0042). With $0.72
spent nothing was at risk, but the estimate now uses the largest check of all 330 (17,344 in,
4,600 out), and both runners stop before a check that could pass the cap, not after.

### What this does and doesn't say

Preliminary reading (inferred): for the app's job, the hosted models beat Llama mainly by
raising far fewer false alarms. GLM 5.2 caught the most, with or without the rule alerts, was
fastest and did best on the quiz. DeepSeek V3.2 was cheapest and the only one to leave both
healthy patients clear every time, but its own alerts caught the fewest problems: it says
less, both right and wrong. Haiku sits between them, is the only hosted model with real
must-not breaks, and cut off its plan in almost half the runs.

It is not yet a model choice. The answer key is a draft; the 110 expected problems are 22
problems run 5 times, so the differences come down to a handful of problems; the word rules
favour long alerts; and nobody has checked the matches by hand except the must-not hits
above. Phase 7 (the doctor's check of the key and the matches) turns this into a result.

## Reproduce

```
python scripts/run_phase2.py --model llama-a100 --repeats 5
python scripts/run_phase2.py --model llama-a100 --repeats 5 --temperature 0
python scripts/run_phase2.py --model deepseek-v3.2 --repeats 5
python scripts/run_afrimedqa.py --model deepseek-v3.2
python scripts/evaluate.py
```

Runs resume where they stopped and refuse to start if the worst-case cost would pass the $5
cap. The A100 needs eduVPN and `LLM_BASE_URL` in `.env`; OpenRouter needs `OPENROUTER_API_KEY`.
