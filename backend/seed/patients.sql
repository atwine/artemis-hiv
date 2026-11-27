-- The app's made-up patients and clinic days: the backup of those database tables (plan 4C.2, 4C.3).
-- Made by `python scripts/patients_backup.py make`; loaded into a new database by
-- `python scripts/patients_backup.py load` after `alembic upgrade head`. The app never reads it.

INSERT INTO "patient" ("patient_id", "position", "name", "sex", "age_years", "art_regimen_as_entered", "complaints_symptoms", "examination_findings", "prior_history", "origin", "added_at") VALUES ('Kintu-Test 001', 7, 'Sarah Nambi', 'F', 36, 'Current ART Regimen: TDF, 3TC, DTG (TLD) for 18 months.', '36-year-old woman presents for routine review. Mentions her clothes no longer fit and she has gained ''a lot of weight'' since starting her current HIV medication. Also feels more tired than usual.', 'BP 138/88 mmHg. Weight 82kg. BMI 32.4 kg/m². Waist circumference 96cm. Acanthosis nigricans noted at neck and axillae. No peripheral oedema.', 'ART History: Switched from TDF/3TC/EFV (used for 3 years) to TLD 18 months ago due to EFV-related side effects (dizziness and vivid dreams).

Baseline Metrics (at TLD switch): BP was 118/74 mmHg; Weight was 65kg; BMI was 25.6 kg/m²; Fasting glucose was 92 mg/dL.

Comorbidities/Family History: HIV diagnosed 2019. No prior DM or HTN. Family history significant for Type 2 Diabetes (mother).', 'seed', '2026-11-27 00:29:49.201811+00:00'::timestamptz) ON CONFLICT DO NOTHING;
INSERT INTO "patient" ("patient_id", "position", "name", "sex", "age_years", "art_regimen_as_entered", "complaints_symptoms", "examination_findings", "prior_history", "origin", "added_at") VALUES ('P001', 1, 'John Doe', 'M', 34, NULL, 'No new complaints', 'Appears well', 'Feels well. Adherence reported good.', 'seed', '2026-11-27 00:29:49.201811+00:00'::timestamptz) ON CONFLICT DO NOTHING;
INSERT INTO "patient" ("patient_id", "position", "name", "sex", "age_years", "art_regimen_as_entered", "complaints_symptoms", "examination_findings", "prior_history", "origin", "added_at") VALUES ('P002', 2, 'Jane Roe', 'F', 29, NULL, 'None reported', 'Stable, no abnormalities noted', 'Stable on ART since 2022. Good adherence.', 'seed', '2026-11-27 00:29:49.201811+00:00'::timestamptz) ON CONFLICT DO NOTHING;
INSERT INTO "patient" ("patient_id", "position", "name", "sex", "age_years", "art_regimen_as_entered", "complaints_symptoms", "examination_findings", "prior_history", "origin", "added_at") VALUES ('P003', 3, 'Sam Kato', 'M', 41, NULL, 'Poor sleep and vivid dreams for several weeks. No suicidal ideation.', 'Alert and oriented, no acute distress', 'Started EFV-based regimen in February 2024.', 'seed', '2026-11-27 00:29:49.201811+00:00'::timestamptz) ON CONFLICT DO NOTHING;
INSERT INTO "patient" ("patient_id", "position", "name", "sex", "age_years", "art_regimen_as_entered", "complaints_symptoms", "examination_findings", "prior_history", "origin", "added_at") VALUES ('P004', 4, 'Amina Nansubuga', 'F', 37, NULL, 'Omusawo, mpulira obulumi mu lubuto (abdominal pain), but no fever', 'Appetite okay, no fever', 'On TLD since March 2023. Generally stable.', 'seed', '2026-11-27 00:29:49.201811+00:00'::timestamptz) ON CONFLICT DO NOTHING;
INSERT INTO "patient" ("patient_id", "position", "name", "sex", "age_years", "art_regimen_as_entered", "complaints_symptoms", "examination_findings", "prior_history", "origin", "added_at") VALUES ('P005', 6, 'Rose Nabirye', 'F', 38, 'TDF/3TC/DTG (TLD) fixed-dose combination once daily. On this regimen for 3 years', '38-year-old woman presents for routine 6-monthly review. No specific complaints. Mentions mild fatigue over the past 2 months which she attributes to her busy work schedule.', 'BP 118/76 mmHg. Weight 64kg (stable). No peripheral oedema. No costovertebral angle tenderness. Otherwise unremarkable.', 'HIV diagnosed 2018. No diabetes, no hypertension. Adherence consistently >95% by pill count. No known allergies. Takes ibuprofen 400mg occasionally for headaches (approximately 2-3 times per week for the past 6 months due to work stress).

Previous ART (moved from Other Medications on 2026-11-25): AZT/3TC/NVP for 2 years (2018-2020), switched to TLD in 2020 due to national guideline transition.', 'seed', '2026-11-27 00:29:49.201811+00:00'::timestamptz) ON CONFLICT DO NOTHING;
INSERT INTO "patient" ("patient_id", "position", "name", "sex", "age_years", "art_regimen_as_entered", "complaints_symptoms", "examination_findings", "prior_history", "origin", "added_at") VALUES ('P006', 5, 'Joan Nakato', 'F', 29, 'TDF/3TC/DTG (TLD) initiated 10 weeks ago.', '29-year-old woman presents for routine 3-month follow-up after initiating ART. No complaints. Feeling well, energy improved since starting treatment.', 'BP 110/70 mmHg. Weight 68kg (pre-pregnancy weight 62kg). Fundal height appropriate for dates. Fetal movements present. No oedema. Urine dipstick negative for protein.', 'HIV diagnosed 10 weeks ago during antenatal screening. Currently 22 weeks pregnant (second pregnancy, first child alive and well). No other medical conditions. No regular medications prior to ART. Taking ferrous sulfate and folic acid as prescribed.', 'seed', '2026-11-27 00:29:49.201811+00:00'::timestamptz) ON CONFLICT DO NOTHING;
INSERT INTO "patient" ("patient_id", "position", "name", "sex", "age_years", "art_regimen_as_entered", "complaints_symptoms", "examination_findings", "prior_history", "origin", "added_at") VALUES ('P007', 8, 'Esther Nakimuli', 'F', 33, NULL, 'No new complaints', 'Appears well. BP 118/76.', 'On ART since 2022. Adherence reported good.', 'seed', '2026-11-27 00:29:49.201811+00:00'::timestamptz) ON CONFLICT DO NOTHING;
INSERT INTO "patient" ("patient_id", "position", "name", "sex", "age_years", "art_regimen_as_entered", "complaints_symptoms", "examination_findings", "prior_history", "origin", "added_at") VALUES ('P008', 9, 'Peter Okot', 'M', 52, NULL, 'No new complaints', 'Appears well. BP 126/82.', 'On ART since 2019, switched to DTG in 2019. Adherence reported good.', 'seed', '2026-11-27 00:29:49.201811+00:00'::timestamptz) ON CONFLICT DO NOTHING;
INSERT INTO "patient" ("patient_id", "position", "name", "sex", "age_years", "art_regimen_as_entered", "complaints_symptoms", "examination_findings", "prior_history", "origin", "added_at") VALUES ('P009', 10, 'Ruth Akello', 'F', 26, NULL, 'No new complaints', 'Appears well.', 'On ART since 2024. Adherence reported good.', 'seed', '2026-11-27 00:29:49.201811+00:00'::timestamptz) ON CONFLICT DO NOTHING;
INSERT INTO "patient_medicine" ("id", "patient_id", "kind", "position", "name") VALUES (1, 'P001', 'art', 0, 'TDF') ON CONFLICT DO NOTHING;
INSERT INTO "patient_medicine" ("id", "patient_id", "kind", "position", "name") VALUES (2, 'P001', 'art', 1, '3TC') ON CONFLICT DO NOTHING;
INSERT INTO "patient_medicine" ("id", "patient_id", "kind", "position", "name") VALUES (3, 'P001', 'art', 2, 'DTG') ON CONFLICT DO NOTHING;
INSERT INTO "patient_medicine" ("id", "patient_id", "kind", "position", "name") VALUES (4, 'P002', 'art', 0, 'TDF') ON CONFLICT DO NOTHING;
INSERT INTO "patient_medicine" ("id", "patient_id", "kind", "position", "name") VALUES (5, 'P002', 'art', 1, '3TC') ON CONFLICT DO NOTHING;
INSERT INTO "patient_medicine" ("id", "patient_id", "kind", "position", "name") VALUES (6, 'P002', 'art', 2, 'DTG') ON CONFLICT DO NOTHING;
INSERT INTO "patient_medicine" ("id", "patient_id", "kind", "position", "name") VALUES (7, 'P003', 'art', 0, 'TDF') ON CONFLICT DO NOTHING;
INSERT INTO "patient_medicine" ("id", "patient_id", "kind", "position", "name") VALUES (8, 'P003', 'art', 1, '3TC') ON CONFLICT DO NOTHING;
INSERT INTO "patient_medicine" ("id", "patient_id", "kind", "position", "name") VALUES (9, 'P003', 'art', 2, 'EFV') ON CONFLICT DO NOTHING;
INSERT INTO "patient_medicine" ("id", "patient_id", "kind", "position", "name") VALUES (10, 'P004', 'art', 0, 'TDF') ON CONFLICT DO NOTHING;
INSERT INTO "patient_medicine" ("id", "patient_id", "kind", "position", "name") VALUES (11, 'P004', 'art', 1, '3TC') ON CONFLICT DO NOTHING;
INSERT INTO "patient_medicine" ("id", "patient_id", "kind", "position", "name") VALUES (12, 'P004', 'art', 2, 'DTG') ON CONFLICT DO NOTHING;
INSERT INTO "patient_medicine" ("id", "patient_id", "kind", "position", "name") VALUES (13, 'P006', 'art', 0, 'TDF') ON CONFLICT DO NOTHING;
INSERT INTO "patient_medicine" ("id", "patient_id", "kind", "position", "name") VALUES (14, 'P006', 'art', 1, '3TC') ON CONFLICT DO NOTHING;
INSERT INTO "patient_medicine" ("id", "patient_id", "kind", "position", "name") VALUES (15, 'P006', 'art', 2, 'DTG') ON CONFLICT DO NOTHING;
INSERT INTO "patient_medicine" ("id", "patient_id", "kind", "position", "name") VALUES (16, 'P005', 'art', 0, 'TDF') ON CONFLICT DO NOTHING;
INSERT INTO "patient_medicine" ("id", "patient_id", "kind", "position", "name") VALUES (17, 'P005', 'art', 1, '3TC') ON CONFLICT DO NOTHING;
INSERT INTO "patient_medicine" ("id", "patient_id", "kind", "position", "name") VALUES (18, 'P005', 'art', 2, 'DTG') ON CONFLICT DO NOTHING;
INSERT INTO "patient_medicine" ("id", "patient_id", "kind", "position", "name") VALUES (19, 'Kintu-Test 001', 'art', 0, 'TDF') ON CONFLICT DO NOTHING;
INSERT INTO "patient_medicine" ("id", "patient_id", "kind", "position", "name") VALUES (20, 'Kintu-Test 001', 'art', 1, '3TC') ON CONFLICT DO NOTHING;
INSERT INTO "patient_medicine" ("id", "patient_id", "kind", "position", "name") VALUES (21, 'Kintu-Test 001', 'art', 2, 'DTG') ON CONFLICT DO NOTHING;
INSERT INTO "patient_medicine" ("id", "patient_id", "kind", "position", "name") VALUES (22, 'P007', 'art', 0, 'TDF') ON CONFLICT DO NOTHING;
INSERT INTO "patient_medicine" ("id", "patient_id", "kind", "position", "name") VALUES (23, 'P007', 'art', 1, '3TC') ON CONFLICT DO NOTHING;
INSERT INTO "patient_medicine" ("id", "patient_id", "kind", "position", "name") VALUES (24, 'P007', 'art', 2, 'DTG') ON CONFLICT DO NOTHING;
INSERT INTO "patient_medicine" ("id", "patient_id", "kind", "position", "name") VALUES (25, 'P008', 'art', 0, 'TDF') ON CONFLICT DO NOTHING;
INSERT INTO "patient_medicine" ("id", "patient_id", "kind", "position", "name") VALUES (26, 'P008', 'art', 1, '3TC') ON CONFLICT DO NOTHING;
INSERT INTO "patient_medicine" ("id", "patient_id", "kind", "position", "name") VALUES (27, 'P008', 'art', 2, 'DTG') ON CONFLICT DO NOTHING;
INSERT INTO "patient_medicine" ("id", "patient_id", "kind", "position", "name") VALUES (28, 'P009', 'art', 0, 'TDF') ON CONFLICT DO NOTHING;
INSERT INTO "patient_medicine" ("id", "patient_id", "kind", "position", "name") VALUES (29, 'P009', 'art', 1, '3TC') ON CONFLICT DO NOTHING;
INSERT INTO "patient_medicine" ("id", "patient_id", "kind", "position", "name") VALUES (30, 'P009', 'art', 2, 'DTG') ON CONFLICT DO NOTHING;
INSERT INTO "art_history" ("id", "patient_id", "position", "start_date", "end_date", "regimen") VALUES (1, 'P001', 0, '2023-01-10'::date, NULL, '["TDF", "3TC", "DTG"]'::jsonb) ON CONFLICT DO NOTHING;
INSERT INTO "art_history" ("id", "patient_id", "position", "start_date", "end_date", "regimen") VALUES (2, 'P002', 0, '2022-06-14'::date, NULL, '["TDF", "3TC", "DTG"]'::jsonb) ON CONFLICT DO NOTHING;
INSERT INTO "art_history" ("id", "patient_id", "position", "start_date", "end_date", "regimen") VALUES (3, 'P003', 0, '2024-02-01'::date, NULL, '["TDF", "3TC", "EFV"]'::jsonb) ON CONFLICT DO NOTHING;
INSERT INTO "art_history" ("id", "patient_id", "position", "start_date", "end_date", "regimen") VALUES (4, 'P004', 0, '2023-03-20'::date, NULL, '["TDF", "3TC", "DTG"]'::jsonb) ON CONFLICT DO NOTHING;
INSERT INTO "art_history" ("id", "patient_id", "position", "start_date", "end_date", "regimen") VALUES (5, 'P007', 0, '2022-03-14'::date, NULL, '["TDF", "3TC", "DTG"]'::jsonb) ON CONFLICT DO NOTHING;
INSERT INTO "art_history" ("id", "patient_id", "position", "start_date", "end_date", "regimen") VALUES (6, 'P008', 0, '2019-06-03'::date, NULL, '["TDF", "3TC", "DTG"]'::jsonb) ON CONFLICT DO NOTHING;
INSERT INTO "art_history" ("id", "patient_id", "position", "start_date", "end_date", "regimen") VALUES (7, 'P009', 0, '2024-01-22'::date, NULL, '["TDF", "3TC", "DTG"]'::jsonb) ON CONFLICT DO NOTHING;
INSERT INTO "lab_result" ("id", "patient_id", "position", "test", "date", "value", "unit", "source") VALUES (1, 'P001', 0, 'viral_load', '2025-10-01'::date, '40', 'copies/mL', 'record') ON CONFLICT DO NOTHING;
INSERT INTO "lab_result" ("id", "patient_id", "position", "test", "date", "value", "unit", "source") VALUES (2, 'P001', 1, 'creatinine', '2024-10-01'::date, '88', 'umol/L', 'record') ON CONFLICT DO NOTHING;
INSERT INTO "lab_result" ("id", "patient_id", "position", "test", "date", "value", "unit", "source") VALUES (3, 'P002', 0, 'viral_load', '2024-09-15'::date, '30', 'copies/mL', 'record') ON CONFLICT DO NOTHING;
INSERT INTO "lab_result" ("id", "patient_id", "position", "test", "date", "value", "unit", "source") VALUES (4, 'P002', 1, 'viral_load', '2025-09-15'::date, '20', 'copies/mL', 'record') ON CONFLICT DO NOTHING;
INSERT INTO "lab_result" ("id", "patient_id", "position", "test", "date", "value", "unit", "source") VALUES (5, 'P002', 2, 'creatinine', '2025-12-15'::date, '76', 'umol/L', 'record') ON CONFLICT DO NOTHING;
INSERT INTO "lab_result" ("id", "patient_id", "position", "test", "date", "value", "unit", "source") VALUES (6, 'P003', 0, 'viral_load', '2025-08-10'::date, '60', 'copies/mL', 'record') ON CONFLICT DO NOTHING;
INSERT INTO "lab_result" ("id", "patient_id", "position", "test", "date", "value", "unit", "source") VALUES (7, 'P004', 0, 'viral_load', '2025-11-05'::date, '25', 'copies/mL', 'record') ON CONFLICT DO NOTHING;
INSERT INTO "lab_result" ("id", "patient_id", "position", "test", "date", "value", "unit", "source") VALUES (8, 'P004', 1, 'creatinine', '2025-11-05'::date, '82', 'umol/L', 'record') ON CONFLICT DO NOTHING;
INSERT INTO "lab_result" ("id", "patient_id", "position", "test", "date", "value", "unit", "source") VALUES (9, 'P007', 0, 'viral_load', '2026-08-12'::date, '<50', 'copies/mL', 'previous') ON CONFLICT DO NOTHING;
INSERT INTO "lab_result" ("id", "patient_id", "position", "test", "date", "value", "unit", "source") VALUES (10, 'P007', 1, 'creatinine', '2026-08-12'::date, '68', 'umol/L', 'previous') ON CONFLICT DO NOTHING;
INSERT INTO "lab_result" ("id", "patient_id", "position", "test", "date", "value", "unit", "source") VALUES (11, 'P008', 0, 'viral_load', '2026-07-20'::date, '<50', 'copies/mL', 'previous') ON CONFLICT DO NOTHING;
INSERT INTO "lab_result" ("id", "patient_id", "position", "test", "date", "value", "unit", "source") VALUES (12, 'P008', 1, 'creatinine', '2026-07-20'::date, '84', 'umol/L', 'previous') ON CONFLICT DO NOTHING;
INSERT INTO "lab_result" ("id", "patient_id", "position", "test", "date", "value", "unit", "source") VALUES (13, 'P009', 0, 'viral_load', '2026-09-02'::date, '<50', 'copies/mL', 'previous') ON CONFLICT DO NOTHING;
INSERT INTO "lab_result" ("id", "patient_id", "position", "test", "date", "value", "unit", "source") VALUES (14, 'P009', 1, 'creatinine', '2026-09-02'::date, '61', 'umol/L', 'previous') ON CONFLICT DO NOTHING;
INSERT INTO "lab_note" ("id", "patient_id", "position", "date", "source", "text") VALUES (1, 'P006', 0, '2026-02-24', 'today', 'Trial--Trial') ON CONFLICT DO NOTHING;
INSERT INTO "lab_note" ("id", "patient_id", "position", "date", "source", "text") VALUES (2, 'P006', 1, '2026-02-24', 'previous', 'Creatinine: 1.1 mg/dL (baseline before ART: 0.8 mg/dL). eGFR: 78 mL/min/1.73m2. Urinalysis: Normal, no protein, no glucose. Viral load: 89 copies/mL (down from 125,000 at diagnosis). CD4: 389 cells/uL (was 312 at diagnosis). Hb: 10.8 g/dL. Phosphate: 3.8 mg/dL (normal).') ON CONFLICT DO NOTHING;
INSERT INTO "lab_note" ("id", "patient_id", "position", "date", "source", "text") VALUES (3, 'P005', 0, '2026-02-24', 'previous', 'Creatinine: 1.4 mg/dL (previous values: 0.9 in 2020, 1.0 in 2021, 1.1 in 2022, 1.2 in 2023). eGFR: 52 mL/min/1.73m2 (CKD-EPI). Urinalysis: Protein 1+, glucose trace. Viral load: <50 copies/mL. CD4: 584 cells/uL. Hb: 12.8 g/dL.') ON CONFLICT DO NOTHING;
INSERT INTO "lab_note" ("id", "patient_id", "position", "date", "source", "text") VALUES (4, 'Kintu-Test 001', 0, '2026-02-24', 'today', 'Glycemic Markers: Fasting glucose 118 mg/dL (impaired); HbA1c 6.1% (pre-diabetic range). Lipid Profile: Total cholesterol 228 mg/dL, LDL 148 mg/dL, HDL 38 mg/dL, Triglycerides 212 mg/dL. Renal/Virological: Creatinine 0.9 mg/dL; Viral load <50 copies/mL; CD4 612 cells/uL.') ON CONFLICT DO NOTHING;
INSERT INTO "clinical_note" ("id", "patient_id", "position", "date", "type", "text") VALUES (1, 'P001', 0, '2026-01-22', 'intake', 'Complaints & Symptoms:
No new complaints

Examination Findings:
Appears well

Prior History:
Feels well. Adherence reported good.') ON CONFLICT DO NOTHING;
INSERT INTO "clinical_note" ("id", "patient_id", "position", "date", "type", "text") VALUES (2, 'P002', 0, '2025-12-15', 'intake', 'Complaints & Symptoms:
None reported

Examination Findings:
Stable, no abnormalities noted

Prior History:
Stable on ART since 2022. Good adherence.') ON CONFLICT DO NOTHING;
INSERT INTO "clinical_note" ("id", "patient_id", "position", "date", "type", "text") VALUES (3, 'P003', 0, '2026-01-22', 'intake', 'Complaints & Symptoms:
Poor sleep and vivid dreams for several weeks. No suicidal ideation.

Examination Findings:
Alert and oriented, no acute distress

Prior History:
Started EFV-based regimen in February 2024.') ON CONFLICT DO NOTHING;
INSERT INTO "clinical_note" ("id", "patient_id", "position", "date", "type", "text") VALUES (4, 'P004', 0, '2026-01-22', 'intake', 'Complaints & Symptoms:
Omusawo, mpulira obulumi mu lubuto (abdominal pain), but no fever

Examination Findings:
Appetite okay, no fever

Prior History:
On TLD since March 2023. Generally stable.') ON CONFLICT DO NOTHING;
INSERT INTO "clinical_note" ("id", "patient_id", "position", "date", "type", "text") VALUES (5, 'P006', 0, '2026-02-24', 'intake', 'Complaints & Symptoms:
29-year-old woman presents for routine 3-month follow-up after initiating ART. No complaints. Feeling well, energy improved since starting treatment.

Examination Findings:
BP 110/70 mmHg. Weight 68kg (pre-pregnancy weight 62kg). Fundal height appropriate for dates. Fetal movements present. No oedema. Urine dipstick negative for protein.

Significant history prior to today''s visit:
HIV diagnosed 10 weeks ago during antenatal screening. Currently 22 weeks pregnant (second pregnancy, first child alive and well). No other medical conditions. No regular medications prior to ART. Taking ferrous sulfate and folic acid as prescribed.') ON CONFLICT DO NOTHING;
INSERT INTO "clinical_note" ("id", "patient_id", "position", "date", "type", "text") VALUES (6, 'P005', 0, '2026-02-24', 'intake', 'Complaints & Symptoms:
38-year-old woman presents for routine 6-monthly review. No specific complaints. Mentions mild fatigue over the past 2 months which she attributes to her busy work schedule.

Examination Findings:
BP 118/76 mmHg. Weight 64kg (stable). No peripheral oedema. No costovertebral angle tenderness. Otherwise unremarkable.

Significant history prior to today''s visit:
HIV diagnosed 2018. No diabetes, no hypertension. Adherence consistently >95% by pill count. No known allergies. Takes ibuprofen 400mg occasionally for headaches (approximately 2-3 times per week for the past 6 months due to work stress).

Previous ART (moved from Other Medications on 2026-11-25): AZT/3TC/NVP for 2 years (2018-2020), switched to TLD in 2020 due to national guideline transition.') ON CONFLICT DO NOTHING;
INSERT INTO "clinical_note" ("id", "patient_id", "position", "date", "type", "text") VALUES (7, 'Kintu-Test 001', 0, '2026-02-24', 'intake', 'Complaints & Symptoms:
36-year-old woman presents for routine review. Mentions her clothes no longer fit and she has gained ''a lot of weight'' since starting her current HIV medication. Also feels more tired than usual.

Examination Findings:
BP 138/88 mmHg. Weight 82kg. BMI 32.4 kg/m². Waist circumference 96cm. Acanthosis nigricans noted at neck and axillae. No peripheral oedema.

Significant history prior to today''s visit:
ART History: Switched from TDF/3TC/EFV (used for 3 years) to TLD 18 months ago due to EFV-related side effects (dizziness and vivid dreams).

Baseline Metrics (at TLD switch): BP was 118/74 mmHg; Weight was 65kg; BMI was 25.6 kg/m²; Fasting glucose was 92 mg/dL.

Comorbidities/Family History: HIV diagnosed 2019. No prior DM or HTN. Family history significant for Type 2 Diabetes (mother).') ON CONFLICT DO NOTHING;
INSERT INTO "encounter" ("id", "patient_id", "date", "visit_type", "note", "orders", "med_changes") VALUES (1, 'P001', '2026-01-22'::date, NULL, 'Routine follow-up. No issues.', '[]'::jsonb, '[]'::jsonb) ON CONFLICT DO NOTHING;
INSERT INTO "encounter" ("id", "patient_id", "date", "visit_type", "note", "orders", "med_changes") VALUES (2, 'P002', '2026-01-22'::date, NULL, 'Routine follow-up. Stable. Discussed DSD eligibility.', '[]'::jsonb, '[]'::jsonb) ON CONFLICT DO NOTHING;
INSERT INTO "encounter" ("id", "patient_id", "date", "visit_type", "note", "orders", "med_changes") VALUES (3, 'P003', '2026-01-22'::date, NULL, 'Complains of insomnia; has vivid dreams. No suicidal ideation.', '[]'::jsonb, '[]'::jsonb) ON CONFLICT DO NOTHING;
INSERT INTO "encounter" ("id", "patient_id", "date", "visit_type", "note", "orders", "med_changes") VALUES (4, 'P004', '2026-01-22'::date, NULL, 'Omusawo, mpulira obulumi mu lubuto, but appetite is okay.', '[]'::jsonb, '[]'::jsonb) ON CONFLICT DO NOTHING;
INSERT INTO "encounter" ("id", "patient_id", "date", "visit_type", "note", "orders", "med_changes") VALUES (5, 'P006', '2026-02-24'::date, NULL, '', '[]'::jsonb, '[]'::jsonb) ON CONFLICT DO NOTHING;
INSERT INTO "encounter" ("id", "patient_id", "date", "visit_type", "note", "orders", "med_changes") VALUES (6, 'P005', '2026-02-24'::date, NULL, '', '[]'::jsonb, '[]'::jsonb) ON CONFLICT DO NOTHING;
INSERT INTO "encounter" ("id", "patient_id", "date", "visit_type", "note", "orders", "med_changes") VALUES (7, 'Kintu-Test 001', '2026-02-24'::date, NULL, '', '[]'::jsonb, '[]'::jsonb) ON CONFLICT DO NOTHING;
INSERT INTO "encounter" ("id", "patient_id", "date", "visit_type", "note", "orders", "med_changes") VALUES (8, 'P007', '2026-11-26'::date, NULL, 'Routine refill visit. Feels well, no missed doses. Continue current regimen.', '[]'::jsonb, '[]'::jsonb) ON CONFLICT DO NOTHING;
INSERT INTO "encounter" ("id", "patient_id", "date", "visit_type", "note", "orders", "med_changes") VALUES (9, 'P008', '2026-11-26'::date, NULL, 'Routine follow-up. No complaints. Taking ART daily. Continue current regimen.', '[]'::jsonb, '[]'::jsonb) ON CONFLICT DO NOTHING;
INSERT INTO "encounter" ("id", "patient_id", "date", "visit_type", "note", "orders", "med_changes") VALUES (10, 'P009', '2026-11-26'::date, NULL, 'Routine refill visit. Feels well. Continue current regimen.', '[]'::jsonb, '[]'::jsonb) ON CONFLICT DO NOTHING;
INSERT INTO "clinic_day" ("date", "clinic", "room", "clinician", "origin") VALUES ('2026-11-26'::date, 'Demo ART Clinic', 'Room 3', 'Dr. A. Okello', 'seed') ON CONFLICT DO NOTHING;
INSERT INTO "appointment" ("id", "date", "time", "patient_id", "name", "origin", "booked_at") VALUES (1, '2026-11-26'::date, '08:40', 'P004', NULL, 'seed', '2026-11-27 00:29:49.298987+00:00'::timestamptz) ON CONFLICT DO NOTHING;
INSERT INTO "appointment" ("id", "date", "time", "patient_id", "name", "origin", "booked_at") VALUES (2, '2026-11-26'::date, '09:05', 'P003', NULL, 'seed', '2026-11-27 00:29:49.298987+00:00'::timestamptz) ON CONFLICT DO NOTHING;
INSERT INTO "appointment" ("id", "date", "time", "patient_id", "name", "origin", "booked_at") VALUES (3, '2026-11-26'::date, '09:30', 'P005', 'Rose Nabirye', 'seed', '2026-11-27 00:29:49.298987+00:00'::timestamptz) ON CONFLICT DO NOTHING;
INSERT INTO "appointment" ("id", "date", "time", "patient_id", "name", "origin", "booked_at") VALUES (4, '2026-11-26'::date, '09:50', 'P006', 'Joan Nakato', 'seed', '2026-11-27 00:29:49.298987+00:00'::timestamptz) ON CONFLICT DO NOTHING;
INSERT INTO "appointment" ("id", "date", "time", "patient_id", "name", "origin", "booked_at") VALUES (5, '2026-11-26'::date, '10:10', 'P007', NULL, 'seed', '2026-11-27 00:29:49.298987+00:00'::timestamptz) ON CONFLICT DO NOTHING;
INSERT INTO "appointment" ("id", "date", "time", "patient_id", "name", "origin", "booked_at") VALUES (6, '2026-11-26'::date, '10:25', 'P008', NULL, 'seed', '2026-11-27 00:29:49.298987+00:00'::timestamptz) ON CONFLICT DO NOTHING;
INSERT INTO "appointment" ("id", "date", "time", "patient_id", "name", "origin", "booked_at") VALUES (7, '2026-11-26'::date, '10:40', 'P009', NULL, 'seed', '2026-11-27 00:29:49.298987+00:00'::timestamptz) ON CONFLICT DO NOTHING;
