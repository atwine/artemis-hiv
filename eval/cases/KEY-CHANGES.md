# Answer key changes for the doctor's review (Phase 7)

The answer key in these case files is a draft written from the guidelines; the doctor reviews it
in Phase 7. This page lists the changes of 2026-11-27, made so the scores stop counting an alert
that names the right problem but recommends the wrong thing (owner's decision: "A, tighten it").

How the key works: each expected problem has groups of words. An alert counts as catching the
problem when it contains at least one word from every group ("renal" matches "renal function").
The change adds one group to each problem below: the action the problem calls for. A "must not"
item is something the app must not advise; a phrase said in the negative ("do not adjust the
TDF dose") doesn't count against it.

Questions for the doctor are marked **Doctor:**.

## Problems that now need their action named

| Case | Problem | What the key expects | Action words now required (any one) |
|---|---|---|---|
| P005 | `tdf_kidney_harm` | Creatinine 0.9 to 1.4 over 4 years on TDF, eGFR 52, protein and glucose in urine: TDF kidney damage; switch TDF | switch, substitute, replace, stop TDF, discontinue, change TDF / the regimen / ART, ABC (abacavir), TAF, AZT (zidovudine) |
| P005 | `nsaid_with_tdf` | Ibuprofen taken regularly with TDF adds to kidney harm; stop it, use paracetamol | stop, avoid, discontinue, paracetamol / acetaminophen, minimise, alternative, limit, reduce |
| MR-KS | `nsaid_with_tdf` | the same | the same |
| P003 | `efv_cns_toxicity` | Insomnia and vivid dreams for weeks on EFV: persistent CNS toxicity; substitute EFV | switch, substitute, replace, change, discontinue, stop, alternative, DTG (dolutegravir) |
| EX4 | `carbamazepine_lowers_dtg` | Carbamazepine lowers DTG levels (viral load up to 1,240): change the anticonvulsant or give DTG 50 mg twice daily | twice daily / a day, 50 mg twice, BD, double, increase, adjust, change, switch, replace, substitute, alternative, stop, discontinue, levetiracetam, valproate, lamotrigine |
| P006 | `iron_with_dtg` | Ferrous sulfate lowers DTG absorption: take DTG 2 hours before or 6 hours after it | hours, separate, apart, timing, space, stagger |
| EX3 | `undertreated_hypothyroidism` | TSH 12.4 on levothyroxine 50 mcg with missed doses: optimise it | increase, adjust, optimise, titrate, dose, adherence, endocrinologist |
| EX3 | `amitriptyline_weight` | Amitriptyline causes weight gain; review with the mental health team | review, switch, change, replace, alternative, stop, reduce, taper, discontinue, mental health, psychiatry |

Left as they were: problems whose action is to check or monitor (their words already say so),
EX2's "hold TLD, then restart" (its words already require holding), and MR-KS's TDF kidney and
bone harm (the key's own action there is "consider replacing TDF", a softer call).

- **Doctor:** P005: should "consider alternative regimens if decline continues" (Llama's usual
  wording) count as recommending the switch? The draft says no: it defers the decision.
- **Doctor:** P005: is TAF an acceptable substitute here, or only ABC or AZT, by the Ugandan
  guideline and what clinics stock?
- **Doctor:** EX4: is "increase the DTG dose" acceptable, or must it say twice daily?
- **Doctor:** EX3: is "review" enough for amitriptyline, or should the alert propose a change?

## New "must not" items

| Case | Item | What the app must not advise | Words that count |
|---|---|---|---|
| P005 | `adjusts_tdf_dose` | Adjusting or reducing the TDF dose: TLD is a fixed-dose combination, and the Ugandan guideline's action for TDF kidney harm is to substitute TDF | adjust (the) TDF (dose), TDF dose adjustment / reduction, reduce (the dose of) TDF, renal dose adjustment |
| MR-KS | `adjusts_tdf_dose` | the same | the same |

- **Doctor:** is there any case where adjusting the TDF dose is right in this clinic (for example
  TDF given on its own, outside TLD)? If so, the item should only apply to TLD.

## Fixed-rule wording that now names the action (2026-11-27)

The app's own fixed rules advised checking rather than acting, so the stricter key no longer
counted them. The owner chose to name the action ("A, name the action"), still as advice for the
clinician to decide, and grounded in the Ugandan guideline.

| Rule | Before | Now | From |
|---|---|---|---|
| "Possible EFV neuropsychiatric side effects" (`efv_sleep_disturbance`) | Consider assessing EFV tolerance and reviewing guideline management options. | Reassure first. If the symptoms persist, consider substituting EFV with DTG (or LPV/r if a suitable DTG formulation is not available) (Uganda HIV Guidelines 2022, p. 269). | p. 269, the EFV row of the side-effects table: "Reassure, If symptoms persist, substitute EFV with DTG or LPV/r (if appropriate DTG formulation is not available)" |

| "NSAID use mentioned while on TDF" (`tdf_nsaid_use`) | Consider reviewing renal risk and ensuring appropriate monitoring. | NSAIDs add to kidney harm. Consider stopping or avoiding the NSAID, especially if kidney function is falling (Uganda Clinical Guidelines 2023, p. 452 and p. 625), with paracetamol for pain instead. Check kidney function; if the GFR is below 60 ml/min, consider substituting TDF with ABC (Uganda HIV Guidelines 2022, p. 270). | UCG 2023 p. 452 (chronic kidney disease): "Avoid nephrotoxic medicines, e.g. NSAIDs, celecoxibs, aminoglycosides, contrast agents"; UCG 2023 p. 625 (pain management): "Do not use NSAIDS in renal impairment"; HIV Guidelines 2022 p. 270, the TDF row: "Do LFTs and RFTs. If deranged (elevated liver enzymes and/or GFR is < 60mls/min) then substitute with ABC If ABC is contraindicated: substitute with AZT" |

- **Doctor:** is "reassure first, then consider substituting EFV with DTG if the symptoms persist"
  how you would want it put for these patients?
- **Doctor:** the NSAID rule cites the Uganda Clinical Guidelines 2023, which the HIV guidelines
  don't replace (they don't mention NSAIDs). Is that appropriate, and should the app search the
  UCG too? (Its AI search uses only the HIV guideline extracts.)
- **Doctor:** paracetamol as the swap is general pain advice: UCG p. 625 lists it as a step-1
  pain medicine and warns about high doses, but doesn't say "use paracetamol instead of NSAIDs
  with TDF". Is it the right thing to suggest here?

## Effect on the saved runs

Every saved run was scored again with the changed key; no model was called. The old and new
numbers side by side are in `eval/phase2/rescore-2026-11-27.md`.
