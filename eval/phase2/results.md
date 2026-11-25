# Phase 2 results (preliminary)

Scored against a draft answer key that no clinician has checked yet (the doctor reviews it in
Phase 7). These numbers steer the work; they are not the app's accuracy.

| Model | Runs | Problems caught | Caught by the AI's own alerts | Alerts that were real | Clear cases left clear | Must-not broken | Same answer across runs | Citations to passages shown | Alert replies read in full | Plans read in full | Median seconds | Cost | Cost per check |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| claude-haiku-5.5 | 55 | 82% (90/110) | 75% (83/110) | 94% (152/162) | 50% (5/10) | 9/45 | 82% | 100% (171/171) | 95% (52/55) | 56% (31/55) | 24.0 | $0.17 | $0.0032 |
| deepseek-v3.2 | 55 | 77% (85/110) | 67% (74/110) | 96% (176/184) | 100% (10/10) | 7/45 | 76% | 100% (119/119) | 100% (55/55) | 100% (55/55) | 27.5 | $0.06 | $0.0011 |
| glm-5.2 | 55 | 86% (95/110) | 84% (92/110) | 92% (194/212) | 80% (8/10) | 8/45 | 82% | 100% (190/190) | 100% (55/55) | 96% (53/55) | 14.1 | $0.41 | $0.0075 |
| llama-a100 | 55 | 80% (88/110) | 68% (75/110) | 81% (175/216) | 0% (0/10) | 6/45 | 85% | 100% (127/127) | 100% (55/55) | 100% (55/55) | 26.4 | $0.00 | $0.0000 |
| llama-a100-before-fix6 | 55 | 75% (83/110) | 68% (75/110) | 83% (168/203) | 0% (0/10) | 7/45 | 85% | 92% (132/144) | 100% (55/55) | 100% (55/55) | 25.3 | $0.00 | $0.0000 |
| llama-a100-t0 | 55 | 78% (86/110) | 69% (76/110) | 82% (178/217) | 0% (0/10) | 5/45 | 98% | 100% (129/129) | 100% (55/55) | 100% (55/55) | 24.8 | $0.00 | $0.0000 |

## Catches per expected problem

Runs in which some alert caught the problem, out of that case's runs.

| Expected problem | claude-haiku-5.5 | deepseek-v3.2 | glm-5.2 | llama-a100 | llama-a100-before-fix6 | llama-a100-t0 |
|---|---|---|---|---|---|---|
| EX2: prerenal_aki | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| EX2: hold_then_restart | 0/5 | 0/5 | 3/5 | 2/5 | 0/5 | 0/5 |
| EX2: electrolytes | 4/5 | 3/5 | 0/5 | 0/5 | 0/5 | 0/5 |
| EX3: undertreated_hypothyroidism | 5/5 | 4/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| EX3: amitriptyline_weight | 1/5 | 0/5 | 1/5 | 0/5 | 0/5 | 0/5 |
| EX4: carbamazepine_lowers_dtg | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| EX4: carbamazepine_toxicity | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| EX4: hyponatraemia | 5/5 | 5/5 | 5/5 | 1/5 | 0/5 | 1/5 |
| EX4: repeat_viral_load | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| Kintu-Test 001: weight_gain | 5/5 | 4/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| Kintu-Test 001: glucose | 5/5 | 4/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| Kintu-Test 001: lipids | 5/5 | 4/5 | 5/5 | 5/5 | 4/5 | 5/5 |
| MR-KS: tdf_tubular_bone_harm | 5/5 | 4/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| MR-KS: nsaid_with_tdf | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| P001: creatinine_overdue | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| P003: efv_cns_toxicity | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| P003: creatinine_never_done | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| P005: tdf_kidney_harm | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| P005: nsaid_with_tdf | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| P005: vl_before_switch | 0/5 | 0/5 | 1/5 | 0/5 | 0/5 | 0/5 |
| P006: iron_with_dtg | 5/5 | 3/5 | 5/5 | 5/5 | 4/5 | 5/5 |
| P006: creatinine_rise | 0/5 | 4/5 | 5/5 | 5/5 | 5/5 | 5/5 |

## AfriMed-QA knowledge check

Exam-style multiple-choice questions on infectious disease or HIV (AfriMed-QA v2). This tests what
a model knows, not the app's job; it only helps narrow the models.

| Model | All questions | HIV-related | Infectious disease | Cost |
|---|---|---|---|---|
| claude-haiku-5.5 | 76% (217/286) | 73% (66/90) | 76% (164/215) | $0.01 |
| deepseek-v3.2 | 77% (220/286) | 73% (66/90) | 78% (167/215) | $0.01 |
| glm-5.2 | 81% (233/286) | 79% (71/90) | 82% (176/215) | $0.04 |
| llama-a100 | 77% (219/286) | 76% (68/90) | 77% (165/215) | $0.00 |
