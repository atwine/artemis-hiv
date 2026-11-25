# Phase 2 results (preliminary)

Scored against a draft answer key that no clinician has checked yet (the doctor reviews it in
Phase 7). These numbers steer the work; they are not the app's accuracy.

| Model | Runs | Problems caught | Alerts that were real | Clear cases left clear | Must-not broken | Same answer across runs | Citations to passages shown | Replies read in full | Median seconds | Cost |
|---|---|---|---|---|---|---|---|---|---|---|
| claude-haiku-5.5 | 55 | 82% (90/110) | 94% (152/162) | 50% (5/10) | 9/45 | 82% | 100% (171/171) | 95% (52/55) | 24.0 | $0.17 |
| deepseek-v3.2 | 55 | 77% (85/110) | 96% (176/184) | 100% (10/10) | 7/45 | 76% | 100% (119/119) | 100% (55/55) | 27.5 | $0.06 |
| glm-5.2 | 55 | 86% (95/110) | 92% (194/212) | 80% (8/10) | 8/45 | 82% | 100% (190/190) | 100% (55/55) | 14.1 | $0.41 |
| llama-a100 | 55 | 80% (88/110) | 81% (175/216) | 0% (0/10) | 6/45 | 85% | 100% (127/127) | 100% (55/55) | 26.4 | $0.00 |
| llama-a100-before-fix6 | 55 | 75% (83/110) | 83% (168/203) | 0% (0/10) | 7/45 | 85% | 92% (132/144) | 100% (55/55) | 25.3 | $0.00 |
| llama-a100-t0 | 55 | 78% (86/110) | 82% (178/217) | 0% (0/10) | 5/45 | 98% | 100% (129/129) | 100% (55/55) | 24.8 | $0.00 |

## AfriMed-QA knowledge check

Exam-style multiple-choice questions on infectious disease or HIV (AfriMed-QA v2). This tests what
a model knows, not the app's job; it only helps narrow the models.

| Model | All questions | HIV-related | Infectious disease | Cost |
|---|---|---|---|---|
| claude-haiku-5.5 | 76% (217/286) | 73% (66/90) | 76% (164/215) | $0.01 |
| deepseek-v3.2 | 77% (220/286) | 73% (66/90) | 78% (167/215) | $0.01 |
| glm-5.2 | 81% (233/286) | 79% (71/90) | 82% (176/215) | $0.04 |
| llama-a100 | 77% (219/286) | 76% (68/90) | 77% (165/215) | $0.00 |
