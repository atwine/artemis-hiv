from __future__ import annotations

from artemis.rules.checks import run_alerts
from artemis.patient.record import build_patient_context
from tests.api_fakes import read_patients


def test_mock_patients_rule_expectations_smoke() -> None:
    patients = [p for p in read_patients() if p["patient_id"] in {"P001", "P002", "P003", "P004"}]

    # Rationale: this is a lightweight smoke test to ensure rules are wired correctly
    # to the demo data.
    outcomes = {}
    for p in patients:
        ctx = build_patient_context(p)
        alerts = run_alerts(ctx)
        outcomes[ctx.patient_id] = "AMBER" if alerts else "GREEN"

    assert outcomes["P001"] == "AMBER"
    assert outcomes["P002"] == "GREEN"
    assert outcomes["P003"] == "AMBER"


def _base_patient(*, note: str, regimen: list[str] | None = None) -> dict:
    # Rationale: build a minimal synthetic patient record for focused rule tests.
    return {
        "patient_id": "TEST",
        "name": "Test Patient",
        "art_regimen_current": regimen or ["TDF", "3TC", "DTG"],
        "visits": [],
        "labs": {
            # Keep creatinine recent so the TDF creatinine overdue rule does not trigger.
            "creatinine": [{"date": "2026-01-01", "value_umol_per_l": 88}],
        },
        "today_encounter": {
            "date": "2026-01-22",
            "note": note,
            "orders": [],
            "med_changes": [],
        },
    }


def test_rule_tdf_nsaid_use_triggers_on_ibuprofen_mention() -> None:
    patient = _base_patient(note="Occasionally uses ibuprofen for back pain.")
    ctx = build_patient_context(patient)
    alerts = run_alerts(ctx)

    assert any(a.alert_id == "tdf_nsaid_use" for a in alerts)


def test_rule_possible_proteinuria_triggers_on_trace_protein_mention() -> None:
    patient = _base_patient(note="Trace protein noted on dipstick.")
    ctx = build_patient_context(patient)
    alerts = run_alerts(ctx)

    assert any(a.alert_id == "possible_proteinuria" for a in alerts)


def test_rule_suboptimal_bp_with_missed_amlodipine_triggers() -> None:
    patient = _base_patient(
        note=(
            "BP is sub-optimally controlled today; patient admits to occasionally missing Amlodipine."
        )
    )
    ctx = build_patient_context(patient)
    alerts = run_alerts(ctx)

    assert any(a.alert_id == "suboptimal_bp_missed_amlodipine" for a in alerts)


# Owner, 2026-11-27 ("A, name the action"): a fixed rule names the guideline's action, still as
# advice for the doctor to decide, grounded in the Ugandan guideline.

def test_the_efv_rule_names_the_guidelines_action():
    from pathlib import Path

    from artemis.evaluation.cases import load_cases
    from artemis.evaluation.scoring import score_run

    p003 = next(p for p in read_patients() if p["patient_id"] == "P003")
    alert = next(a for a in run_alerts(build_patient_context(p003)) if a.alert_id == "efv_sleep_disturbance")
    assert "If the symptoms persist, consider substituting EFV with DTG" in alert.message
    assert "Uganda HIV Guidelines 2022, p. 269" in alert.message
    case = next(c for c in load_cases(Path(__file__).resolve().parents[1] / "eval" / "cases") if c.case_id == "P003")
    rule_alert = {"title": alert.title, "message": alert.message, "source": "rule", "evidence": {}}
    assert "efv_cns_toxicity" in score_run(case, [rule_alert]).caught


def test_the_nsaid_rule_names_the_action_and_where_it_comes_from():
    """Owner, 2026-11-27: the Uganda HIV guidelines don't cover NSAIDs, so the rule also cites the
    Uganda Clinical Guidelines 2023 (owner: "it's okay to add the UCG to cite it along with the HIV
    guidelines"); the doctors confirm it in Phase 7."""
    from pathlib import Path

    from artemis.evaluation.cases import load_cases
    from artemis.evaluation.scoring import score_run

    cases = {c.case_id: c for c in load_cases(Path(__file__).resolve().parents[1] / "eval" / "cases")}
    for pid in ("P005", "MR-KS"):
        patient = next((p for p in read_patients() if p["patient_id"] == pid), None) or cases[pid].patient
        alert = next(a for a in run_alerts(build_patient_context(patient)) if a.alert_id == "tdf_nsaid_use")
        for words in ("stopping or avoiding the NSAID", "paracetamol", "Uganda Clinical Guidelines 2023, p. 452 and p. 625",
                      "Check kidney function", "substituting TDF with ABC", "Uganda HIV Guidelines 2022, p. 270"):
            assert words in alert.message, (pid, words)
        rule_alert = {"title": alert.title, "message": alert.message, "source": "rule", "evidence": {}}
        assert "nsaid_with_tdf" in score_run(cases[pid], [rule_alert]).caught, pid
