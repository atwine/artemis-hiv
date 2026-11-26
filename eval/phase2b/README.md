# Phase 2B: the guideline search revamp (2026-11-25 to 2026-11-26)

What we tried to make the app hand the AI the right guideline passage for each patient's actual
problems, what we kept, and what we learned. Every number has a row in `docs/decisions.tsv`, with
the rule for keeping or dropping each fix written there before its run. The answer key is a draft
no clinician has checked yet (Phase 7), so these numbers steer the work; they are not the app's
accuracy.

Labels: **measured** means counted from the saved files; **inferred** means a reading of them.

## The question

Phase 2 measured the app's alerts, not whether the right passage reached the AI. So a miss could
not be blamed on "looked in the wrong place" or "read the right page and reasoned badly".

## How it was measured

- **A gold passage per problem** (`eval/cases/*.json`, drafted from the guidelines): 17 of the 22
  planted problems have one; 5 are in no guideline. Plus 20 standalone clinician-style questions
  (`questions.json`).
- **The search checker** (`scripts/check_retrieval.py`) runs the app's own search and reports, for
  each problem, whether the gold passage came back and at what rank. It also searches each problem
  with its answer-key summary (the "ideal" track: what perfect search wording could reach) and each
  gold quote word for word (the self-check, which proves the passage is findable at all). It refuses
  to measure if the search model did not load.
- **End to end** (`scripts/run_phase2.py`, scored by `scripts/evaluate.py`): the whole app on the
  11 cases, 3 runs each at temperature 0. "Own catches" counts the AI's own alerts.

## What we found first (measured)

- **The diagnosis** (`diagnosis.md`): the right passage reached the AI for only 3 of 17 problems. When
  it did, the AI caught the problem 98% of the time; when it did not, 72%. So search was a real lever.
- **Other countries' guidance was crowding Uganda's out.** The index mixed Ugandan, South African and
  WHO passages with no country label.

## What we kept

| Change | Why it stayed (measured) |
|---|---|
| Ugandan guidance only (owner's rule; `artemis/guidelines/sources.py`) | Questions found in the top 5 went from 3/20 to 13/20. It costs some catches that only foreign guidance covered (GLM 84% to 80%, Llama 69% to 59%; GLM's comparison also moves from temperature 0.2 to 0), and 10 of 22 problems now have no Ugandan passage at all |
| The AI writes the patient's search questions (fix 5q) | The right passage reaches the AI for 6/12 problems instead of 4/12 (GLM writing them), equal to the best this index allows even with perfect wording. Kept by the owner although one short of its bar; GLM end to end unchanged at 80% |
| A search model that fails to load switches the AI review and the plan step off, with a red banner (G33) | An alert built on the near-random fallback search looks as sure as a good one |
| An edited guideline file gets a fresh stored index (G37) | The stored index is named with a fingerprint of the guideline text, so old passages are never served |
| Citations name the printed page ("Uganda HIV guidelines 2022, p.255"; G36) | The old "p.22" was the page's position in our extract; checked against the PDF on three pages |
| The measuring tools: the checker, its self-check, the ideal track, saved-question replay | They made every keep-or-drop call a number |

## What we tried and dropped (measured, each by the rule written before its run)

| Fix | What it was | Search result | End to end (GLM own catches) |
|---|---|---|---|
| 5a | one search per drug and problem | cases 3/12 (4 before) | not run |
| 5c | keyword search beside meaning search | self-check 34/34, but questions 10/20, cases 3/12 | not run |
| 5b | pieces cut along the guideline's sections | ideal 7/12, but questions 11/20, cases 5/12 | not run |
| 5d | search model bge-small-en-v1.5 | cases 7/12, ideal 7/12, but questions 11/20 | not run |
| 5e | small re-ranker (ms-marco-MiniLM) | self-check 34/34, but questions 10/20 | not run |
| 5a2 | the AI reads whole passages, not their first 480 characters | (no search change) | 80%, unchanged (85% needed); healthy left clear 1/6 (3/6) |
| 5f | search model Qwen3-Embedding-0.6B | questions 15/20, ideal 9/12, self-check 32/34: the best search | 74% (80% needed); healthy left clear 1/6 |

## What it tells us (inferred)

1. **Better search did not mean better catches.** Twice the app found more of the right passages
   (5q, 5f) and the AI caught no more problems; with Qwen3 it caught fewer and raised more alerts on
   healthy patients. More passages that read as relevant seem to give the AI more to flag and pull
   it off some planted problems. The end-to-end check stays the deciding one.
2. **Small, web-trained search models lack medical knowledge.** Three fixes (5b, 5d, 5e) helped
   exact-wording searches and lost clinician-worded ones; read by hand, the lost passages were really
   wrong (asked about an older epilepsy medicine with dolutegravir, one returned viral-load monitoring).
3. **The index itself caps search.** Even searched with the answer key's own words, only 6 to 9 of
   12 problems reach their passage. The next real gain is probably one record per recommendation
   (plan item 8.5, with the doctor), not more search tuning.

## The final check (measured)

The kept setup on the three shortlisted models, 3 runs per case, temperature 0. The rule, written
before the runs: no model's own catches fall more than 5 points below its Uganda-only baseline.

| Model | Own catches (Uganda-only baseline) | Real alerts | Healthy left clear | Must-not broken | Cost a check |
|---|---|---|---|---|---|
| GLM 5.2 (`glm-5.2-t0-5q`) | 80% (80%) | 88% | 3/6 | 6/27 | $0.0093 |
| Llama 3.3 70B on the A100 (`llama-a100-t0-2b`) | 55% (59%) | 77% | 0/6 | 6/27 (9/27) | free |
| DeepSeek V3.2 (`deepseek-v3.2-t0-2b`) | 61% (67% in Phase 2, all four guidelines, temperature 0.2; not judged) | 91% | 5/6 | 4/27 | $0.0018 |

Llama passes, just (4 points down, 5 allowed). DeepSeek catches fewer problems than GLM but is the
most careful: the most real alerts and the most healthy patients left clear (inferred: a trade-off,
not a winner). The Llama and GLM runs used the index before the
printed-page change (G36); the DeepSeek run used the index with printed pages.

## Owner's decisions in this phase

Ugandan guidance only (G32); keep the AI question step; stop the AI review when the search model
fails (G33); printed pages in citations (G36); keep the guidelines as plain text, records later
(2B.7); keep only the files the app uses in the public repository (2B.6); keep Chroma with its four
accepted advisories (2B.5). The laptop now keeps model weights on drive D and runs search on its
graphics card (same results as the processor, all 42 searches identical).

Spent on OpenRouter in Phases 2 and 2B: see `docs/decisions.tsv` (under the $5 cap).
