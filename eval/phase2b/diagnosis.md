# Search diagnosis: was the passage shown, and was the problem caught?

From the saved Phase 2 runs (Llama at temperature 0, the others at 0.2). Catches count the AI's own alerts.

| Problem | Gold passage shown to the AI | Llama | GLM | DeepSeek | Haiku |
|---|---|---|---|---|---|
| EX2:prerenal_aki | no | 5/5 | 5/5 | 5/5 | 5/5 |
| EX2:hold_then_restart | no | 0/5 | 3/5 | 0/5 | 0/5 |
| EX2:electrolytes | not in the guidelines | 0/5 | 0/5 | 3/5 | 4/5 |
| EX3:undertreated_hypothyroidism | not in the guidelines | 5/5 | 5/5 | 4/5 | 5/5 |
| EX3:amitriptyline_weight | not in the guidelines | 0/5 | 1/5 | 0/5 | 1/5 |
| EX4:carbamazepine_lowers_dtg | yes | 5/5 | 5/5 | 5/5 | 5/5 |
| EX4:carbamazepine_toxicity | not in the guidelines | 5/5 | 5/5 | 5/5 | 5/5 |
| EX4:hyponatraemia | not in the guidelines | 1/5 | 5/5 | 5/5 | 5/5 |
| EX4:repeat_viral_load | no | 5/5 | 5/5 | 5/5 | 5/5 |
| Kintu-Test 001:weight_gain | no | 5/5 | 5/5 | 4/5 | 5/5 |
| Kintu-Test 001:glucose | yes | 5/5 | 5/5 | 4/5 | 5/5 |
| Kintu-Test 001:lipids | no | 5/5 | 5/5 | 4/5 | 5/5 |
| MR-KS:tdf_tubular_bone_harm | no | 5/5 | 5/5 | 4/5 | 5/5 |
| MR-KS:nsaid_with_tdf | no | 5/5 | 5/5 | 3/5 | 5/5 |
| P001:creatinine_overdue | no | 5/5 | 5/5 | 1/5 | 3/5 |
| P003:efv_cns_toxicity | yes | 5/5 | 5/5 | 5/5 | 5/5 |
| P003:creatinine_never_done | no | 0/5 | 2/5 | 0/5 | 0/5 |
| P005:tdf_kidney_harm | no | 5/5 | 5/5 | 5/5 | 5/5 |
| P005:nsaid_with_tdf | no | 0/5 | 5/5 | 5/5 | 5/5 |
| P005:vl_before_switch | no | 0/5 | 1/5 | 0/5 | 0/5 |
| P006:iron_with_dtg | no | 5/5 | 5/5 | 3/5 | 5/5 |
| P006:creatinine_rise | no | 5/5 | 5/5 | 4/5 | 0/5 |

- Passage shown: yes. The AI caught 59 of 60 problem-runs (98%).
- Passage shown: no. The AI caught 202 of 280 problem-runs (72%).
- Passage shown: not in the guidelines. The AI caught 64 of 100 problem-runs (64%).
