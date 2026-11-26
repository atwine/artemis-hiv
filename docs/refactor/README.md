# Keeping track of the restructure

The code is moving out of one big `app.py` into folders, piece by piece, as each Phase 1 fix
touches it (owner's choice, 2026-11-25). These files make sure nothing gets lost or confused
along the way.

| File | What it holds |
|---|---|
| `code-map.tsv` | One row per function: what it does in plain words, where it is now, where it's going, and its status (`stays`, `to-move` or `moved`). |
| `moves.tsv` | One row per move, rewrite or deletion: from where, to where, and the proof that nothing broke. |
| `../decisions.tsv` | One row per decision and per finished fix, with the reason and the result. |
| `../audit/` | The Phase 1 audit: every fault found, grouped by cause, and the owner's decisions. |

## Where code is going

```
artemis/            the app's logic, with no screen code
  patient/          reading a record: labs, medicines, dates
  rules/            the fixed safety rules
  guidelines/       splitting, storing, searching guideline text
  ai/               talking to the model, reading its replies
  plan/             the management plan
  visit.py          runs one visit check from start to finish
  screen_text.py    the wording every screen shows (docs/screen-checklist.md)
  review.py         alert review and finalize rules
ui/                 the Streamlit screen only
api/                FastAPI (Phase 4)
web/                Next.js (Phase 5)
```

`ui/` holds only the Streamlit screen. It isn't called `ui/streamlit/`, because a folder named
`streamlit` can be mistaken for the Streamlit library itself.

## The routine at the end of every fix or decision

1. **Before deleting or moving anything**, find every caller (search the code) and make sure
   the new home exists and is tested.
2. Add a row to `moves.tsv` for each function moved, rewritten or deleted, with its proof.
   The proof is a named test, the golden check, or "no callers".
3. Update `code-map.tsv`: new functions get a row, and moved ones change status.
4. Add a row to `../decisions.tsv` with the decision or fix, the reason and the result.
   If the fix showed a new kind of silent failure, add it to `../lessons-learned.md`.
   Tick the fix in `../PLAN.md` (Phase 1) once its tests pass.
5. Run the checks. All must pass before the commit:

   ```bash
   python scripts/check_code_map.py
   python -m pytest -q
   ```

`check_code_map.py` fails when:
- a function has no map row
- a map row names a function that no longer exists
- a deleted or moved function still exists in its old place
- a move points to a home that doesn't exist
- a row is missing its proof

The test suite runs the same check, so GitHub fails too.
