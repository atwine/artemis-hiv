# Not searched: guidelines from outside Uganda

The app gives Ugandan clinics Ugandan guidance only (owner, 2026-11-25). These files were moved
out of `Data/MarkDown Files/` so they can never reach the guideline search, and the search
database was rebuilt from the Ugandan files alone.

- `SAHCS_Adult_ART_2024.md`: Southern African HIV Clinicians Society adult ART guideline, 2024.
- `WHO_guidelines.extraction.md`: WHO consolidated HIV guidelines.

They are kept for reference only. Some draft answer-key quotes in `eval/cases/` point at the
SAHCS file; the search check counts those problems as not in the searched guidelines. To use a
file here again, it must be added to `artemis/guidelines/sources.py` and moved back, which is the
owner's call.
