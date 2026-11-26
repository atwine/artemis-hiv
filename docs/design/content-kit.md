# Content kit for the Phase 3 mockups

Every design direction uses this same made-up content, so the owner compares layouts, not
data. All people, IDs and the clinic are made up. The clinical picture follows test patient
P005 (`eval/cases/P005.json`) and what GLM 5.2 actually raised for it in Phase 2
(`eval/phase2/runs/glm-5.2/P005__run1.json`), re-cited to Ugandan guidance.

## Header and setting

- App name: **ARTEMIS-HIV**. Tagline if needed: "Decision support for HIV clinic visits".
  Footer or about text: "Decision support only. Made-up patients. Not for clinical use."
- Clinic: **Demo ART Clinic · Room 3**. Clinician signed in: **Dr. A. Okello** (made up).
- Today: **Thu 26 Nov 2026**.

## Clinic list (today)

| Time  | ID   | Name                | Age/Sex | Regimen        | Status after checks                         |
|-------|------|---------------------|---------|----------------|---------------------------------------------|
| 08:40 | P004 | Amina Nansubuga     | 29 F    | TDF/3TC/DTG    | GREEN, finalized 08:52                      |
| 09:05 | P003 | Sam Kato            | 45 M    | TDF/3TC/EFV    | AMBER (1 alert), finalized 09:18            |
| 09:30 | P005 | **Rose Nabirye**    | 38 F    | TDF/3TC/DTG    | **RED (5 alerts), 2 reviewed, not finalized** (the case we open) |
| 09:50 | P006 | David Mugisha       | 61 M    | ABC/3TC/DTG    | INCOMPLETE (AI review failed, rules only)   |
| 10:10 | P007 | Esther Nakimuli     | 33 F    | TDF/3TC/DTG    | Not checked yet                             |
| 10:25 | P008 | Peter Okot          | 52 M    | TDF/3TC/DTG    | Not checked yet                             |
| 10:40 | P009 | Ruth Akello         | 26 F    | TDF/3TC/DTG    | Not checked yet                             |

Useful counts for a header: 7 booked, 3 checked, 2 finalized, 1 left in red.

## The case: Rose Nabirye, P005

- 38, female, weight 64 kg (stable), BP 118/76 mmHg.
- HIV diagnosed 2018. Adherence above 95% by pill count. No diabetes, no hypertension, no
  known allergies.
- **Current ART:** TDF/3TC/DTG (TLD), once daily, since 2020 (switched under the national
  transition).
- **Previous ART:** AZT/3TC/NVP, 2018 to 2020.
- **Other medicines:** ibuprofen 400 mg, 2 to 3 times a week for 6 months (headaches from
  work stress).
- **Complaints today:** routine 6-monthly review. Mild tiredness for 2 months, which she puts
  down to work.
- **Exam today:** no oedema, no costovertebral angle tenderness, otherwise unremarkable.

### Labs (one row per result, always with a unit)

| Test        | Date        | Value | Unit           | Note                 |
|-------------|-------------|-------|----------------|----------------------|
| Creatinine  | 2020-03-10  | 0.9   | mg/dL          |                      |
| Creatinine  | 2021-03-16  | 1.0   | mg/dL          |                      |
| Creatinine  | 2022-04-05  | 1.1   | mg/dL          |                      |
| Creatinine  | 2023-05-02  | 1.2   | mg/dL          |                      |
| (none)      | 2024, 2025  |       |                | no creatinine taken  |
| Creatinine  | 2026-11-26  | 1.4   | mg/dL          | today                |
| eGFR (CKD-EPI) | 2026-11-26 | 52  | mL/min/1.73 m² | today, below 60      |
| Urine protein (dipstick) | 2026-11-26 | 1+ | (dipstick) | today            |
| Urine glucose (dipstick) | 2026-11-26 | trace | (dipstick) | today          |
| Viral load  | 2026-05-12  | <50   | copies/mL      | suppressed           |
| CD4         | 2026-05-12  | 584   | cells/µL       |                      |
| Haemoglobin | 2026-11-26  | 12.8  | g/dL           |                      |

### Today's note, as the clinician wrote it (Assessment & Plan)

> Routine 6-monthly review. Mild fatigue x 2 months, attributes to work. BP 118/76, wt 64 kg.
> VL suppressed (May). Plan: continue TLD, 3-month refill. Paracetamol for headaches.
> Review in 3 months.

## Guideline passages (real text, Ugandan guidance only)

Source document: **Consolidated Guidelines for the Prevention and Treatment of HIV and AIDS in
Uganda, 2022** (Ministry of Health). Page numbers are read from our text extraction; check
them against the printed PDF before Phase 5.

- **G1.** Section 6.14 Common drug toxicities in HIV care · Table 78: Toxicities/side effects
  of commonly used ARVs and recommended substitutions · p. 270. TDF row.
  - Major toxicity: "Chronic kidney disease, acute kidney injury and Fanconi syndrome"
  - Signs: "Lower back pain, change in urine volume … Exhaustion or extreme fatigue"
  - Suggested management: "Do LFTs and RFTs. If deranged (elevated liver enzymes and/or GFR
    is < 60mls/min) then substitute with ABC. If ABC is contraindicated: substitute with AZT"
- **G2.** Table 83: Laboratory monitoring for Active Pharmacovigilance in non-sentinel sites
  · p. 260. TDF row: "Do Serum creatinine & eGFR for experienced patient on TDF every 12
  months"

There is **no Ugandan passage** about ibuprofen or NSAIDs with TDF in our guideline files.
That is a useful honest state to design: "No Ugandan guideline passage cited. Based on the
drug's known effects; check before acting."

Citation display: the format is undecided (printed page, section heading, or both), so show
both, e.g. "Uganda HIV Guidelines 2022 · Table 78 · p. 270".

## Alerts for P005 (overall status RED)

Order by severity. Review state in the "results" screen is as listed (2 of 5 reviewed).

1. **Kidney function falling on TDF** · Drug harm · High · AI review · cites G1
   - Finding: Creatinine has risen from 0.9 (2020) to 1.4 mg/dL today; eGFR is 52, below 60;
     protein 1+ in the urine. On TDF since 2020. This fits TDF kidney toxicity. Against it:
     no diabetes, no hypertension; ibuprofen may also contribute.
   - Recommended action: Check the viral load is still suppressed, then substitute TDF with
     ABC (AZT if ABC is contraindicated). Repeat kidney function tests.
   - Patient values to show beside it: creatinine series, eGFR 52, urine protein 1+, on TDF
     since 2020.
   - Review state: **Accepted** by Dr. A. Okello, 09:47.
2. **Ibuprofen with TDF while kidney function falls** · Drug or condition clash · High ·
   AI review · no Ugandan passage
   - Finding: Ibuprofen 400 mg 2 to 3 times a week for 6 months, on TDF, with eGFR 52.
     NSAIDs reduce kidney blood flow and add to TDF's kidney harm.
   - Recommended action: Stop ibuprofen; use paracetamol for headaches.
   - Review state: unreviewed.
3. **Today's plan continues TDF despite eGFR 52** · Plan gap · High · AI review · cites G1
   - Finding: The plan says "continue TLD" although eGFR is below 60, where the guideline
     says to substitute TDF. The plan does not mention the kidney results or the ibuprofen.
   - Recommended action: Address the kidney results in today's plan.
   - Review state: unreviewed.
4. **Creatinine not checked in 2024 or 2025** · Missed monitoring · Moderate · Rule check ·
   cites G2
   - Finding: On TDF, creatinine and eGFR are due every 12 months. The last result before
     today was 2023-05-02, 3.5 years ago.
   - Recommended action: Set a yearly creatinine and eGFR reminder for this patient.
   - Review state: **Overridden**, reason "Already done, not documented", comment "Results
     from a private lab in 2024, not in the file", 09:49.
5. **NSAID use mentioned while on TDF** · Drug or condition clash · Moderate · Rule check
   - Finding: "ibuprofen" appears in the notes of a patient on TDF.
   - Recommended action: Review kidney risk and monitoring.
   - Review state: unreviewed. (A design may group it with alert 2 as "same problem".)

Finalize is locked: "3 alerts left to review".

## AI management plan vs the clinician's plan

Regimen decision badge: **Switch** (red). "Substitute TDF with ABC: ABC/3TC/DTG, once viral
load suppression is confirmed."

| Problem | AI suggests | Clinician's plan | Verdict |
|---|---|---|---|
| Kidney function falling on TDF | Substitute TDF with ABC after confirming VL | "continue TLD" | **Differs from your plan** |
| Viral load before switching | Repeat VL now (last May 2026) | "VL suppressed (May)" | **Partly in your plan** |
| Ibuprofen | Stop; paracetamol instead | "Paracetamol for headaches" | **Partly in your plan** |
| Kidney follow-up | Repeat creatinine, eGFR and urine protein in 4 to 6 weeks | (nothing) | **Not in your plan** |
| Refill and review | 3-month refill, review in 3 months | "3-month refill … review in 3 months" | **Matches your plan** |

Monitoring list: creatinine and eGFR, urine protein, viral load. Counselling: stop ibuprofen;
report less urine, back pain or swelling.

## Saved visit record (audit)

- Visit V-2026-11-26-P005-01 · checks run 09:42:10, finalized 09:58:31 (after all five are
  reviewed).
- Model: GLM 5.2 (hosted, made-up patients only) · temperature 0 · AI review: complete ·
  10 guideline passages shown to the AI, 1 cited.
- App version: 3f9c2e1. Rules version: same.
- Each alert: title, kind, severity, source, decision, reason, comment, time.
- Note as checked, and a warning if today's note was edited after the checks ran.

## Edge states

- **INCOMPLETE (P006, David Mugisha).** "AI review failed: the model server did not answer.
  Only rule checks are shown. Issues the AI would have raised may be missing." Offer "Run
  the AI review again". One rule alert or none.
- **GREEN (P004, Amina Nansubuga).** "No alerts. 6 rule checks and the AI review found nothing."
  Show what was checked: regimen, 4 medicines, 9 lab results, 3 notes, 10 guideline passages.
- **Note changed since checks.** "You edited the note after the checks ran (09:42). Run the
  checks again to update the alerts."

## Add a patient case

- Fields: ID, name, age, sex, visit date, visit type.
- ART regimen pick-list: TDF, 3TC, FTC, DTG, ABC, AZT, EFV, NVP, LPV/r, ATV/r, TAF, with
  common fixed-dose combinations (TLD = TDF/3TC/DTG) as shortcuts. **No "Select all".**
- Previous ART with dates. Other medicines (name, dose, how often).
- Labs: a table, one row per result: test (pick-list), date, value, unit (pick-list that
  depends on the test), plus "Add result". Show 3 filled rows and one empty.
- Complaints, exam findings, history.
