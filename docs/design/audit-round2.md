# Screen audit, round 2 (2026-11-26)

Scope: every screen of the five directions in the Paper file "Artemis-HIV" after the
declutter split, checked against the avatar checklist and the screen budget in `brief.md`
and against `content-kit.md`. "Before declutter" frames were skipped. 71 screens and five
flow maps were looked at.

How the evidence was gathered:
- **Measured** means seen in a Paper screenshot (1366 x 768 frames) or read from Paper's
  style data. Font sizes come from a style search across the whole file: no real content is
  set below 11px except the numbered markers on D5 S5a (10px) and status-icon glyphs
  (9 to 10px, which are icons, not text). The D4 timeline and futures charts are drawn as
  SVG, so their text sizes are read from the screenshots (about 11 to 12px), not from style data.
- **Inferred** means it follows from what the screens show but was not tested (for example,
  what a button would do).
- Nothing in Paper was changed. No screenshot came back black.

How a screen "passes the budget fully": at most 3 blocks in the working area, at most 1
open decision, exactly 1 primary-looking button (0 is allowed on a progress screen), no fact
shown twice, at most 2 tags per alert row, and the safety floor kept on alert decision
screens. A small repeat (the same count in two places) still counts as a fail, because rule 3
says a fact appears once.

## Verdicts

| Direction | Screens passing fully | Verdict in one line |
|---|---|---|
| 01 Triage Board | 12 of 14 | The cleanest and closest to the rules; its alert screen passes the five-second test; only small repeats and content slips are left. |
| 02 Guided Review | 12 of 14 | Calm, clear and the safest to interrupt; the plan screen opens several decisions at once, override takes two taps, and half the add-case steps are not drawn. |
| 03 Evidence Desk | 11 of 13 | The best evidence view (number, line, guideline sentence); the edge states are two screens squeezed into one frame and Finalize has no confirm step. |
| 04 Patient Timeline | 8 of 15 | The most original but the busiest; several budget breaks, small chart text, a plan screen with no main button, and missing paths. |
| 05 Note Co-pilot | 8 of 15 | A strong idea, but the note takes half of every screen so core screens run to four blocks; the alert-to-words anchor is ambiguous and the AI can rewrite the note. |

## 01 Triage Board

Flow map (F0): clear; every step from the brief is drawn, each arrow names its button.
Five-second test on S4b: passes (measured): RED and "2 of 5 reviewed" in the header, the
alert title, "52" on a ruler with the 60 guideline mark, one blue "Accept alert".

| Screen | Blocks | Decisions | Primary | Shown twice | Tags/row | Smallest real text | Floor | Notes |
|---|---|---|---|---|---|---|---|---|
| S1 Clinic list | 2 (queue, selected-patient panel) | 1 | 1 | none | 2 | 11px table headers | n/a | Pass. Side panel is fine on the clinic list. |
| S2a Visit before checks | 3 | 1 | 1 | none | n/a | 11px labels | n/a | Pass. Says "12" lab results; the kit has 11 (measured count of kit rows). |
| S2b Lab results | 1 | 0 | 0 (side screen) | none | n/a | 11px headers | n/a | Pass. One row per test with a trend sentence, not one row per result. |
| S3 Checks running | 3 | 0 | 0 | none | 2 | 11-12px | n/a | Pass. "12 lab results" again. Honest "no colour yet" line. |
| S4a Visit summary | 3 | 1 | 1 | "3 alerts left to review" in the banner and on the locked Finalize | 2 | 12px | yes | **Fail** (rule 3, minor). Row order puts alert 3 before alert 2. |
| S4b Alert | 3 | 1 | 1 | none | 2 | 11px labels, ruler numbers | **yes** | Pass. |
| S4c Override reason | 3 + reason panel (replaces button row) | 1 | 0 (reasons save on tap) | none | 2 | 11px | **yes** | Pass. One-tap reasons, "Cancel, go back". |
| S5 Plan comparison | 3 | 1 | 1 | "Differs from your plan" and "continue TLD" in the regimen card and in row 1 | 1 verdict | 11px headers | n/a | **Fail** (rule 3). Verdicts use red/amber/green. |
| S6a Finalize | 3 | 1 | 1 | none | 2 | 12px | n/a | Pass. Real confirm step. |
| S6b Saved visit record | 3 (banner, table, "what was checked") | 1 | 1 | none | 2 (11px) | 11px "High · AI review" | n/a | Pass. NSAID alert shown as "Overridden: other"; other directions show "Accepted" (kit leaves it open). |
| S7a INCOMPLETE | 3 | 1 | 1 | none | n/a | 12px | n/a | Pass. Header differs from other visit screens (no patient bar). |
| S7b GREEN | 2 | 1 | 1 | none | n/a | 12px | n/a | Pass. Shows what was read. |
| S8a Add case: patient, medicines | 1 form | 1 | 1 | none | n/a | 12px | n/a | Pass. Pick-list, TLD shortcut, no "Select all". |
| S8b Add case: labs, note | 1 form | 1 | 1 | none | n/a | 11-12px | n/a | Pass. One row per result with unit, 3 filled + 1 empty. **No Assessment and plan field.** |

Hidden leftover keyboard-badge nodes ("R", "Esc") sit inside S2a and S3 with `display: none`
(measured); not visible, harmless, worth deleting before handoff.

Top fixes:
1. On S5, drop the "Your plan says / Differs from your plan" side box from the regimen card, since row 1 of the table already says it.
2. On S4a, cut "3 alerts are left to review before you can finalize" from the banner; the locked Finalize button already says it.
3. Change "12 lab results" to 11 on S2a and S3 so the counts match the content kit.
4. Add an "Assessment and plan" box to S8b, because the plan comparison has nothing to compare without it.
5. Give the plan verdicts on S5 neutral colours so red, amber and green only ever mean alert status.

## 02 Guided Review

Flow map (F0): clear and the easiest to follow; but it names add-case steps (Details,
Complaints and exam, Check and save) that are not drawn (measured: only S8a Medicines and
S8b Lab results exist). Five-second test on S4b: passes (measured): RED in the track bar, a
large title, "52" beside a "Below 60, the guideline's line" pill, one dark "Accept alert",
and the plain question "Does this alert apply to Rose today?".

| Screen | Blocks | Decisions | Primary | Shown twice | Tags/row | Smallest real text | Floor | Notes |
|---|---|---|---|---|---|---|---|---|
| S1 Clinic list | 1 | 1 | 1 | none | 2 | 12-13px | n/a | Pass. "you left off here" on Rose's row. |
| S2a Record | 2 | 1 | 1 | none | n/a | 12px | n/a | Pass. Lab table one row per result with units, gap row shown. |
| S2b Today's note | 1 | 1 | 1 | none | n/a | 12px | n/a | Pass. |
| S3 Checks running | 3 | 0 | 1 (locked, "in about 6 s") | none | n/a | 12px | n/a | Pass. 11 lab results, matching the kit. |
| S4a Results | 1 list | 1 | 1 | none | 2 | 12px | yes | Pass on budget, but the heading "Five alerts to review" contradicts "2 reviewed" and "3 alerts left". |
| S4b Alert | 3 | 1 | 1 | position shown as "Alert 3 of 5" and as track dots; "Table 78" in two lines | 2 | 12px | **yes** | **Fail** (rule 3, minor). |
| S4c Override reason | 3 | 1 | 1 (locked "Save override") | none | 2 | 12px | **yes** | Pass on budget; **reason takes two taps** (pick, then Save), against checklist point 5. |
| S5 Plan | 2 | **4** (three "Add to my plan" plus Next) | 1 | none | 1 verdict | 12px | n/a | **Fail** (rule 2). "Add to my plan" writes AI text into the note after the checks ran. Verdicts reuse status colours and shapes. |
| S6a Sign and save | 1 | 1 | 1 | none | n/a | 12px | n/a | Pass. Summary letter, real confirm. |
| S6b Saved record | 3 | 1 | 1 ("Run checks again") | none | 2 | 12px | n/a | Pass. "Show times and kinds" keeps tags off the rows. |
| S7a INCOMPLETE | 2 | 1 | 1 | none | n/a | 12px | n/a | Pass. "Continue with rule checks only" locked behind a tick box, a good honest gate. |
| S7b GREEN | 1 | 1 | 1 | none | n/a | 12px | n/a | Pass. Shows "Sign and save: unlocked" for Amina, whom the kit lists as finalized 08:52 (minor). |
| S8a Add case: medicines | 2 | 1 | 1 | none | n/a | 12px | n/a | Pass. No "Select all", stated on screen. |
| S8b Add case: lab results | 1 | 1 | 1 | none | n/a | 12px | n/a | Pass. One row per result, unit list follows the test. |

Top fixes:
1. Make each override reason save on one tap and drop the separate locked "Save override" button on S4c.
2. On S5, offer one "Add to my plan" decision at a time (or move it to its own step) and say that adding text means the checks must run again.
3. Change the S4a heading to "3 alerts left to review" so it matches the track bar and the list.
4. On S4b show the alert position once (track dots or "Alert 3 of 5") and cite Table 78 once.
5. Draw the missing add-case steps (Details, Complaints and exam with an Assessment and plan field, Check and save).

## 03 Evidence Desk

Flow map (F0): clear, written as text routes; Finalize goes straight from the header to the
saved record with no confirm step (measured in the map: "Finalize visit (unlocks when 0
left)" leads to S6). Five-second test on S4c: passes (measured): RED in the header, title,
"52" and "TDF" highlighted, a drawn line to the highlighted "GFR is < 60mls/min" sentence,
a filled "Accept".

| Screen | Blocks | Decisions | Primary | Shown twice | Tags/row | Smallest real text | Floor | Notes |
|---|---|---|---|---|---|---|---|---|
| S1 Clinic list | 1 | 1 | 1 | none | 2 | 12-13px | n/a | Pass. |
| S2 Visit before checks | 3 | 1 | 1 | none | n/a | 12-13px | n/a | Pass. Gap years drawn as a hatched lab row. |
| S3 Checks running | 2 | 0 | 0 | none | n/a | 12px | n/a | Pass. Says "12" lab results; the kit has 11. |
| S4a Visit summary | 3 | 1 | 1 (Finalize locked in header) | none | 2 | 12-13px | yes | Pass. "Shown 10 passages, cited 1" stated honestly. |
| S4b Alert, no Ugandan passage | 3 | 1 | 1 | none | 2 | 13px | **yes** | Pass. Honest dashed "No Ugandan guideline passage cited". |
| S4c Alert on the desk | 3 | 1 | 1 | none | 2 | 13px | **yes** | Pass. |
| S4d Override reason | 3 | 1 | 0 (reasons save on tap) | none | 2 | 13px | **yes** | Pass. One-tap reasons, "Cancel". |
| S4e Guideline page | 1 | 0 | 1 ("Back to the alert") | none | n/a | 12px | n/a | Pass. Full Table 78 TDF row, page caveat shown. |
| S5 Plan comparison | 3 | 1 | 1 ("Finalize visit") | none | 1 verdict | 12px | n/a | Pass on budget. Verdict symbols are good, but colours are red/amber/green. |
| S6 Finalize and visit record | 2 | 1 | 1 | finalized time 09:58:31 in the header and in the record card | 2 (+ "rests on" chip in the audit table) | 12px | n/a | **Fail** (rule 3, minor). The note-changed banner is about 130px tall for one line. |
| S7 Edge states | 2 half-screens in one frame | 2 | 2 | n/a | n/a | 12px | n/a | **Fail.** INCOMPLETE and GREEN share one 1366 frame, so neither is a real screen and neither has the visit header. |
| S8a Add case: patient, medicines | 1 form | 1 | 1 | none | n/a | 12px | n/a | Pass. No "select all", TLD shortcut. |
| S8b Add case: labs, note | 1 form | 1 | 1 | none | n/a | 12px | n/a | Pass. **No Assessment and plan field.** |

Top fixes:
1. Split S7 into two real screens, INCOMPLETE and GREEN, each inside the normal visit header.
2. Add a "Finalize this visit?" confirm step between the Finalize button and the saved record.
3. On S6, show the finalized time once and shrink the note-changed banner to its content.
4. Change the lab count on S3 from 12 to 11.
5. Add an Assessment and plan field to S8b and give plan verdicts neutral colours.

## 04 Patient Timeline

Flow map (F0): clear and complete as a map, but it marks S8c (today's note) as not drawn,
gives INCOMPLETE no way to finalize (only "Run the AI review again"), and sends GREEN
straight to Finalize with no plan step (measured in the map). Five-second test on S4b:
partly passes: RED and "2 of 5 reviewed" are visible and Accept is clear, but the 22px serif
guideline quote is bigger than the patient's "52", and the left card is mostly empty space
(measured).

| Screen | Blocks | Decisions | Primary | Shown twice | Tags/row | Smallest real text | Floor | Notes |
|---|---|---|---|---|---|---|---|---|
| S1 Clinic list | 1 | 1 | 1 | "Add patient case" as a header tab and as a button | 2 | 12px | n/a | **Fail** (rule 3, minor). |
| S2 Visit before checks | 2 | 1 | 1 | BP 118/76 and 64 kg in the header, exam and plan; ibuprofen in a lane and in the note | n/a | 11-12px chart labels | n/a | **Fail** (rule 3). The chart labels "60 below this, substitute TDF" before any check has run. |
| S3 Checks running | 2 | 0 | 0 | none | 2 ("Moderate · Rule") | 11-12px | n/a | Pass. |
| S4a Timeline with flags | 1 chart + legend | 1 | 1 | "3 open alerts", "Locked: 3 alerts left" and "2 of 5 reviewed" | 1-2 per flag | 11-12px (SVG) | yes | **Fail** (rule 3). Dense chart; flags are click targets, not hover. |
| S4b Flag opened | 3 | 1 | 1 | position as "Alert 3 of 5" and as chips; the 60 threshold as a chart label and in the quote | 2 | 12px | **yes** | **Fail** (rule 3). |
| S4c Override reason | **4** (alert, numbers, guideline, reason panel) | 1 | 1 | as S4b | 2 | 12px | **yes** | **Fail** (rule 4). Reason takes two taps (radio, then Save). |
| S5a Two futures | 2 | 1 | 1 ("Edit today's note") | none | 1 verdict | **about 11px** for plan steps (SVG) | n/a | Pass on budget, but real content is below the 14px body rule; a 140px empty band sits above the card. |
| S5b Plan as a list | 2 | 0 | **0** | none | 1 verdict | 12px chips | n/a | **Fail** (rule 1: no main button, only "Back"). |
| S6a Finalize visit | 1 (dialog) | 1 | 1 | none | n/a | 13px | n/a | Pass. |
| S6b Saved visit record | 2 | 1 | 1 | "Finalized 09:58:31" in the chip and in the record | n/a | 12px | n/a | **Fail** (rule 3, minor). |
| S6c Reopened, note changed | 2 | 1 | 1 | none | n/a | 12px | n/a | Pass on budget; the status (RED) is missing from this visit screen. |
| S7a INCOMPLETE | 2 | 1 | 1 | none | n/a | 13px | n/a | Pass on budget; **no "Finalize with rule checks only"**. |
| S7b GREEN | 2 | 1 | 1 | none | n/a | 13px | n/a | Pass. Offers Finalize for Amina, whom the kit lists as finalized 08:52 (minor). |
| S8a Add case: patient, regimen | 3 cards | 1 | 1 | none | n/a | 12px | n/a | Pass. **No "Other medicines" field** here or on S8b. |
| S8b Add case: lab results | 1 | 1 | 1 | none | n/a | 12px | n/a | Pass. One row per result, unit after the test. |

Top fixes:
1. On S4c, make reasons save on one tap and fold the reason panel into the alert card so the screen stays at three blocks.
2. Give S5b a main button and close the empty band above the futures card on S5a.
3. Raise the plan-step text in the S5a futures chart from about 11px to at least 14px, or leave the detail to S5b.
4. Add "Finalize with rule checks only" to S7a, an "Other medicines" field to add-case, and draw S8c.
5. Remove the repeats: the duplicate "Add patient case" on S1, BP and weight three times on S2, and the triple "3 left" count on S4a.

## 05 Note Co-pilot

Flow map (F0): clear; the plan step is optional ("See plan suggestions" before "Sign
note"), and "Sign note" finalizes straight from the header with no confirm screen (S4d says
"Finalizes the visit and saves the record"). Five-second test on S4a: partly passes: RED and
"3 alerts left" are in the header and Accept is clear, but the note takes the left half, and
two phrases are highlighted ("continue TLD" in violet, "Paracetamol for headaches" with a red
underline) while the connector line ends on that shared line, so which words the open alert
is about is ambiguous (measured).

| Screen | Blocks | Decisions | Primary | Shown twice | Tags/row | Smallest real text | Floor | Notes |
|---|---|---|---|---|---|---|---|---|
| S1 Clinic list | 1 | 1 | 1 | none | 2 | 12px | n/a | Pass. Uses "signed" where the kit and brief say "finalized". |
| S2a Note before checks | 3 | 1 | 1 | none | n/a | 12-13px | n/a | Pass. 11 lab results, matching the kit. |
| S2b Record | **4** (note, medicines, history, labs) | 1 | 1 | none | n/a | 12-13px | n/a | **Fail** (rule 4). |
| S3 Checks running | 3 | 0 | 0 | none | 2 | 12-13px | n/a | Pass. Note locked while checks run. |
| S4a Note with margin notes | **4** (note, reviewed strip, open alert, Next row) | 1 | 1 | none | 2 | 12-13px | **yes** | **Fail** (rule 4). Anchor ambiguity, above. |
| S4b Override reason | **4** | 1 | 1 (locked "Save reason") | none | 2 | 12-13px | **yes** | **Fail** (rule 4). Two taps, though the cover says "one-tap reasons". |
| S4c Next note, no Ugandan passage | 3 | 1 | 1 | none | 2 | 12-13px | **yes** | Pass. Groups the NSAID rule alert with the ibuprofen alert, which the kit allows. |
| S4d Ready to sign | 3 | 1 | 1 | "all reviewed" in the header, the strip and the card | n/a | 12-13px | n/a | **Fail** (rule 3). |
| S5a Plan suggestions | 3 | 1 | 1 ("Accept change") | "all reviewed" under Sign note and in the status chip | 1 verdict | **10px** numbered markers in the note | n/a | **Fail** (rule 3; markers below the 11px label floor). "Accept change" writes the regimen switch into the note. |
| S6a Saved visit record | 3 | 1 | 1 | finalized time in the record and the signature line | 1 source | 12px | n/a | **Fail** (rule 3, minor). |
| S6b Reopened, note changed | 3 | 1 | 1 | none | n/a | 12px | n/a | Pass. "As checked / As signed" switch is a good touch. |
| S7a INCOMPLETE | 3 | 1 | 1 | none | n/a | 12-13px | n/a | Pass. "Sign without the AI review" asks to confirm. |
| S7b GREEN | 2 | 1 | 1 | none | n/a | 13px | n/a | Pass. |
| S8a New case: note | 1 form | 1 | 1 | none | n/a | 13px | n/a | Pass on budget, but **no Assessment and plan field** in a direction built on the note. |
| S8b New case: medicines, labs | **4** cards | 1 | 1 | none | n/a | 12-13px | n/a | **Fail** (rule 4, minor; it is a form). |

The note sheet and several cards (S1 table, S7a, S7b) run past the bottom edge of the 768px
frame without a closing edge (measured). It reads as a sheet that continues, not a bug, but
on a real 768px screen the signature line sits at the very bottom.

Top fixes:
1. Make reason chips save on one tap on S4b, as the cover promises, and drop "Save reason".
2. On S4a, highlight only the open alert's words and end the connector line on those words.
3. Bring S2b and S4a back to three blocks (fold the "Next" row into the reviewed strip; merge medicines and history).
4. Add an Assessment and plan field to the new-case note on S8a.
5. Make "Accept change" say that it edits the note after the checks (and so asks for checks again), and raise the 10px markers to at least 11px.

## Problems across all five

1. **Plan verdicts borrow the alert colours** (measured in all five). "Partly in your plan"
   is amber, "Differs" is red with the "!" square in D2, D4, D5, "Matches" is green with the
   tick. The brief keeps red, amber and green for clinical status; Harriet could read
   "Partly in your plan" as an AMBER alert. D3's symbols (=, ≈, ≠, +) are the best shape
   idea; they just need neutral colours.
2. **The AI can write into the clinician's note** (measured: D2 S5 "Add to my plan", D5 S5a
   "Accept change"). This edits the note after the checks ran, which by the brief's own rule
   should trigger "note changed, run checks again", and it puts the AI's regimen switch into
   a signed note. D4 does the opposite ("Only your note is saved as the plan"). This is a
   decision for the owner, not a styling fix.
3. **Override reasons take two taps in three directions** (measured: D2 S4c, D4 S4c, D5 S4b),
   against checklist point 5 ("Reasons are one tap"). D1 and D3 save on tap.
4. **Add a patient case has no place for the plan** (measured: D1 S8b, D3 S8b, D5 S8a have
   Complaints, Exam and History only; D2 and D4 do not draw the note step). The kit lists only
   those three fields, but without an Assessment and plan the plan comparison has nothing to
   compare (inferred). Worth adding to the kit.
5. **Counts drift from the kit** (measured): D1 and D3 say 12 lab results, D2 and D5 say 11
   (the kit has 11 rows). Small, but a clinician checking "what was read" would notice.
6. **Finalize without a confirm step** in D3 and D5 (inferred from their flow maps), against
   checklist point 7 ("Nothing irreversible without a clear confirmation"). D1, D2 and D4 have
   one.
7. **Small text**: labels are kept at 11px or more everywhere except D5's 10px plan markers
   (measured). Real content below 14px appears mainly in D4's charts (about 11px, SVG) and in
   12px sub-lines under alert titles in saved records (D1, D3, D4).
8. **GREEN state for Amina**: D2 and D4 show her as not yet finalized, while the kit says
   finalized 08:52 (measured). Minor, but it changes which button the screen offers.

## Missing steps (from each flow map and the frames)

| Step | D1 | D2 | D3 | D4 | D5 |
|---|---|---|---|---|---|
| Clinic list | yes | yes | yes | yes | yes |
| Visit before checks | yes | yes | yes | yes | yes |
| Checks running | yes | yes | yes | yes | yes |
| Alert review + override reason | yes, one tap | yes, two taps | yes, one tap | yes, two taps | yes, two taps |
| Plan comparison | yes | yes | yes | yes (two screens) | yes, optional |
| Finalize (confirm) | yes | yes | **no confirm** | yes | **no confirm** |
| Saved record + note changed | yes | yes | yes | yes | yes |
| INCOMPLETE | yes | yes | composite frame | yes, **no finalize path** | yes |
| GREEN | yes | yes | composite frame | yes, no plan step | yes |
| Add case: regimen, no "Select all" | yes | yes | yes | yes | yes |
| Add case: labs one row per result with unit | yes | yes | yes | yes | yes |
| Add case: other medicines | yes | yes | yes | **missing** | yes |
| Add case: note with plan | no plan field | **not drawn** | no plan field | **not drawn** (S8c) | no plan field |

## Anything broken

- No black screenshots; the file rendered on every call.
- No clipped text or overlapping elements found.
- Layout slips (measured): D4 S5a has an empty band of about 140px above the futures card;
  D3 S6's note-changed banner is far taller than its one line; D3 S7 puts two screens in one
  frame; D5's note sheet and some cards run past the 768px bottom edge with no closing edge.
- Leftover hidden nodes (measured): D1 S2a and S3 still contain keyboard-badge nodes set to
  `display: none`.
