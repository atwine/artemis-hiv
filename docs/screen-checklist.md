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

| Result | When | The screen must show |
|---|---|---|
| `ok` | The AI replied and its alerts were read | Its alerts beside the rule alerts; no extra banner |
| `not_run` | The AI review was switched off | Rule alerts only; if none, a blue note that the AI review was off |
| `failed` | The model server did not answer | Amber banner: AI review failed, only rule checks shown, issues may be missing |
| `unreadable` | The reply could not be read as a list of alerts | Amber banner, same as `failed`, with its own reason |
| `cut_off` | The reply stopped before it finished | Amber banner: AI review incomplete; the alerts read are shown, others may be missing |
| `partly_read` | Part of the reply could not be read | Amber banner, same as `cut_off`, with its own reason |
| `search_unavailable` | The guideline search model did not load (G33) | Red banner: guideline search unavailable, AI review off, check the search model setting. The plan step does not run either; rule alerts show no guideline references |

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
- **Guidance is Ugandan only** (G32): every passage comes from the register in
  `artemis/guidelines/sources.py`.

## 4. Review and finalize

- Each alert is acknowledged or overridden; an override needs a reason from `OVERRIDE_REASONS`
  (`artemis/review.py`), and "Other" needs a comment.
- Finalize stays disabled until every alert is handled, with the note `FINALIZE_BLOCKED`
  (`can_finalize` in `artemis/review.py`).

## 5. Always

- The disclaimer `DISCLAIMER`: "Decision support only. Clinician retains final authority.
  Synthetic data only."
- Errors shown on screen stay generic; details go to the server log, never the model server's
  address.
