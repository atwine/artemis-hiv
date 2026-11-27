# Screen checklist

Every state a visit check can end in, and what any screen must show for it: the Streamlit app
today, the FastAPI backend (Phase 4) and the Next.js site (Phase 5). The owner asked for this on
2026-11-26 so the pieces fit together with nothing missing when they are joined.

How it stays true:

- **The wording lives in one place**, `artemis/screen_text.py`. Every screen takes its text from
  there instead of writing its own. The API sends that text; the website displays it.
- **The lists live in one place**, `artemis/statuses.py` (re-exported by `artemis/visit.py`, and
  small so scripts can read it fast): `AI_REVIEW_OUTCOMES` and `STATUSES`. A visit
  result with any other value is refused (`AnalysisResult.__post_init__`), and the API's types are
  built from these lists, like the override reasons in `artemis/review.py`.
- **A test keeps this file honest**: `tests/test_screen_checklist.py` fails if a result or status is
  missing below, or if one has no banner wording.
- **Phase 5's check** walks this list in Chrome, one item at a time, with a screenshot each.

## 1. How the AI review ended (`AI_REVIEW_OUTCOMES`)

| Result | When | The screen must show | Record label | Day card label |
|---|---|---|---|---|
| `ok` | The AI replied and its alerts were read | Its alerts beside the rule alerts; no extra banner | Complete | (its alerts) |
| `not_run` | The AI review was switched off | Rule alerts only; if none, a blue note that the AI review was off | Switched off for this check | (its alerts) |
| `failed` | The model server did not answer | Amber banner: AI review failed, only rule checks shown, issues may be missing | Failed: the model server did not answer | AI review failed |
| `unreadable` | The reply could not be read as a list of alerts | Amber banner, same as `failed`, with its own reason | Failed: the reply could not be read | AI review failed |
| `cut_off` | The reply stopped before it finished | Amber banner: AI review incomplete; the alerts read are shown, others may be missing | Incomplete: the reply was cut off | AI review incomplete |
| `partly_read` | Part of the reply could not be read | Amber banner, same as `cut_off`, with its own reason | Incomplete: part of the reply could not be read | AI review incomplete |
| `search_unavailable` | The guideline search model did not load (G33) | Red banner: guideline search unavailable, AI review off, check the search model setting. "Compare plans" makes no plan either (503); rule alerts show no guideline references | Not run: guideline search unavailable | Guideline search unavailable |

The two labels are `AI_REVIEW_LABELS` and `AI_REVIEW_CARD_LABELS` in `artemis/screen_text.py` (owner,
2026-11-26: the backend sends them, in `ai_review_label` and `ai_review_card_label`, on the visit
check, the saved visit, a patient's past checks and the day board).

## 2. The overall result (`STATUSES`)

| Status | When | The screen must show |
|---|---|---|
| `RED` | At least one high or critical alert | Red banner with the number of alerts |
| `AMBER` | Alerts, none high or critical | Amber banner with the number of alerts (called YELLOW before 2026-11-26; older records read as AMBER) |
| `GREEN` | No alerts and the AI review finished cleanly or was off | Green "no alerts" (AI ran) or blue "no rule check triggered, AI off" |
| `INCOMPLETE` | No alerts, but the AI review did not finish cleanly | Blue "no rule check was triggered", under the AI review's own banner; never green |

The banner for every pair is `status_banners(status, ai_review_result, alert_count)`.

## 3. Each alert

- **Heading** says who raised it: `alert_heading`, e.g. "Alert (Rule check): Creatinine monitoring
  overdue while on TDF" or "Alert (AI review): ...".
- **References** (`alert_references`): an AI alert lists the passages it was shown and cited; a
  passage it cites but was not shown is marked "not among the passages the AI was given". A rule
  alert lists the passages a search found for it, headed "Related passages".
- **A citation** names the guideline and its printed page (G36): `citation_line`, e.g. "Uganda HIV
  Guidelines 2022 · p. 255" (the design's look, owner 2026-11-26: capital G, a middle dot with
  spaces, "p." and a space; no table or section number until plan item 8.5). Never the page's
  position in our extract file.
- **The value box** (`alert_values`): the patient values the alert is about, each as recorded
  (label, value, unit, date), the latest on or before the visit date. A creatinine rule shows
  creatinine and eGFR; any other alert shows the tests its own words name. None when none is named.
- **The key sentence** (`key_sentence`): the one guideline sentence closest to the alert, picked by
  code from its passages; none when nothing is close enough (owner, 2026-11-26: no AI change).
- **Guidance is Ugandan only** (G32): every passage comes from the register in
  `artemis/guidelines/sources.py`.

## 4. Review and finalize

- Each alert is acknowledged or overridden; an override needs a reason from `OVERRIDE_REASONS`
  (`artemis/review.py`), and "Other" needs a comment.
- Finalize stays disabled until every alert is handled, with the note `FINALIZE_BLOCKED`
  (`can_finalize` in `artemis/review.py`).

- A visit check whose record could not be saved: an amber banner, `RECORD_NOT_SAVED` ("This check
  could not be saved, so its alerts cannot be decided here."), from `record_banners` (owner,
  2026-11-26). The API sends it in `banners`; the Streamlit screen keeps its own sentence, since
  there a Finalize still saves to the file.

## 4b. The management plan ("Compare plans")

Made only on demand for a saved visit (owner, 2026-11-27: "A, only Compare plans"), saved, and
sent back on the saved visit (`plan`, null before the first). Read by `artemis/plan/view.py`:
only what the AI actually said.

| `outcome` | When | The screen must show |
|---|---|---|
| `made` | A readable plan came back | The regimen badge (`regimen.label`: Switch, Hold temporarily, Continue, or a grey "Needs review" with the AI's own words in `regimen.text`), its reason, then each problem with what the AI suggests and its `verdict_label`, then monitoring and counselling |
| `made`, with `issues` | It is readable but failed the app's own checks | The same, under a warning: `PLAN_ISSUES_NOTE` ("This plan failed the app's own checks. Treat it with care.") in `issues_note` |
| `failed` | No readable plan (the model server failed, or the reply could not be read after its retries) | `PLAN_FAILED` in `error` ("The management plan could not be produced."); never the details |

- Verdict labels: "Matches your plan", "Differs from your plan", "Partly in your plan", "Not in
  your plan", "Not assessed" (the AI gave none), and "No plan to compare" on every item when the
  note had no plan.
- No plan is made when the guideline search is unavailable (503, G33) or no model server is set
  up (503). A plan counts toward the same limit as visit checks (6 a minute, 429).
- `saved: false`: the plan is shown but could not be saved.
- Pressing "Compare plans" again: a plan that passed its checks is shown again with no AI call;
  a failed or flagged one is tried again (owner, 2026-11-27: "A, keep a good plan").

## 5. Always

- The disclaimer `DISCLAIMER`: "Decision support only. Clinician retains final authority.
  Synthetic data only."
- Errors shown on screen stay generic; details go to the server log, never the model server's
  address.
