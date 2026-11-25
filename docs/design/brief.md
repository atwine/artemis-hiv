# ARTEMIS-HIV design brief (Phase 3)

Status: draft, 2026-11-26. The owner asked for five independent design directions instead of
three (2026-11-26), so this brief is the shared ground all five stand on. Corrections from the
owner go straight into this file.

Paper file: **Artemis-HIV** (Projects folder), one page per direction, page `00 · Start here`
for the overview. Shared made-up content: `docs/design/content-kit.md`.

## Who uses it

- HIV clinicians (medical officers, clinical officers, nurses who prescribe ART) in Ugandan
  ART clinics. Busy: a clinic day can mean dozens of patients, a few minutes each.
- On a shared clinic workstation or laptop, often with a small screen. We design every screen
  at **1366 x 768** (a common clinic laptop size; a guess, to confirm with Dr Kintu in Phase 7).
  Nothing that decides the visit may sit below the fold.
- Not designers or IT people. Plain clinical words, no AI jargon, no "chunks" or "tokens".
- Secondary readers: whoever audits a visit later (a supervisor, the doctor checking the
  evaluation, the owner's portfolio visitors).

## The avatar every screen is judged against

The owner's rule (2026-11-26): the experience must be flawless for clinicians, simple to
understand and never cluttered. Every screen is critiqued against this one person. She is a
made-up composite; the details are assumptions to check with Dr Kintu in Phase 7.

**Harriet, a clinical officer at a busy ART clinic.**
- Sees 40 to 60 patients on a clinic day, a few minutes each, with a queue outside the door.
  Interrupted often: a phone, a colleague, a patient's question.
- Knows HIV care and the Ugandan guidelines well. Knows the computer less well: confident with
  a mouse and a form, not with shortcuts, hidden menus or hover-only details.
- English is her working language, not always her first. Short plain sentences beat clever
  wording. Abbreviations she uses daily (TDF, eGFR, VL, TLD) are fine; software and AI words
  are not.
- Trusts the Ministry of Health guidelines; is wary of a computer telling her what to do.
  She will act on an alert only if she can see why in a glance: her patient's number next to
  the guideline line.
- Works on a shared 1366 x 768 screen, sometimes in glare, sometimes on a slow or dropping
  connection.

**What she needs from every screen (the critique checklist)**
1. **The five-second test.** In five seconds she can say what state the patient is in and
   what the one next thing to do is. One primary action per screen, visibly the main one.
2. **Nothing she has to hunt for.** No hover-only information, no hidden menus for core steps,
   no keyboard-only actions (shortcuts are a bonus, never the only way).
3. **Calm by default.** Show only what this step needs; the rest one click away. No more than
   three levels of text size and two accent colours on a screen besides the status colours.
   White space over boxes. If something can go, it goes.
4. **Readable at arm's length.** Body text 14 to 16px, key numbers larger, high contrast.
5. **Few, clear decisions.** Each alert asks one question (accept or override). Reasons are one
   tap. Nothing is typed unless "Other".
6. **Safe to be interrupted.** She can leave mid-review and come back to exactly where she was,
   with what is done and what is left obvious.
7. **No surprises.** Buttons say what they do ("Finalize visit", not "Submit"). Locked buttons
   say why they are locked. Nothing irreversible without a clear confirmation.

## What the app does (the workflow every design must show)

1. **Clinic list.** Today's patients. Each shows whether checks have run, the overall status
   (RED / AMBER / GREEN / INCOMPLETE) and whether the visit is finalized. Entry to add a
   patient case.
2. **Patient visit, before checks.** The record (regimen, other medicines, dated labs with
   units, dated notes, previous ART) and today's note (complaints, exam, assessment and plan).
   One main button: run the checks.
3. **Checks running.** Rule checks finish at once; the AI review takes about 15 seconds
   (GLM 5.2 averaged 14 s in Phase 2). Show progress honestly, and what is being read.
4. **Results and alert review (the core screen).** Overall status. Each alert has a kind
   (drug harm, drug or condition clash, missed monitoring, plan gap), a severity, its source
   (rule check or AI review), the finding, the recommended action, and the Ugandan guideline
   passage it rests on, shown beside the patient values it is about. The clinician reviews
   each alert on the alert itself: **Accept**, or **Override** with a reason ("Other" needs a
   comment). Finalize stays locked until every alert is reviewed.
5. **AI management plan vs the clinician's plan,** item by item: matches your plan, partly in
   your plan, differs from your plan, not in your plan, not assessed, or no plan to compare.
   The regimen decision is a badge: Switch (red), Hold (amber), Continue (green), Needs review
   (grey). Never a green "Continue" when the AI didn't clearly say continue.
6. **Finalize and the saved visit record (audit).** What was checked, what the screen showed,
   what the clinician decided and why, which model, which app version, when. A saved visit can
   be reopened without asking the AI again; if today's note changed since, the screen says so.
7. **Edge states.** AI review failed or cut off: status INCOMPLETE, only rule alerts shown, and
   the screen says issues may be missing. GREEN: no alerts, plus what was checked, so a quiet
   screen never looks like a skipped check.
8. **Add a patient case.** Regimen pick-list (TDF, 3TC, DTG, ABC, AZT, EFV, NVP, LPV/r, ATV/r,
   TAF, FTC) with **no "Select all"**; other medicines; labs entered **one row per result**:
   test, date, value, unit.

Authentication comes later (Phase 4/5). Designs show a clinician name in the header but no
sign-in screens.

## Principles (from the plan)

- **Clinicians first.** The screen answers "what must I do for this patient now?" before
  anything else. Debug detail (passage ids, distances, raw JSON) is never on the main view.
- **Penda-style red / amber / green.** Only red interrupts. Amber is visible but never blocks
  reading. Green is quiet. An accepted alert is never shown again as new.
- **Review on the alert itself,** not in a separate list at the bottom of the page.
- **Guideline text beside the patient values.** The clinician sees the rule and the number it
  applies to without switching screens.
- **Colour never works alone.** Every status has a word and a shape as well (red = square
  "!", amber = triangle, green = circle tick, incomplete = dashed circle), for colour-blind
  users and grey-scale printouts.
- **Honest about the AI.** Say which findings came from the fixed rules and which from the AI;
  say when the AI cited no Ugandan passage; never let a failed AI review look like a clean one.
- **Ugandan guidance only** (owner's rule, 2026-11-25). Citations name the document, edition,
  section or table, and printed page. Whether the final citation shows the printed page, the
  section heading, or both is still open (Phase 2B); designs show both so the owner can choose.

## Override reasons (a proposal, from the Kenyan alert trial in "Ideas borrowed")

Today: Already addressed, Not applicable, Will address later, Patient declined, Other.
Proposed: Already done, not documented · Test not available here · Not right for this
patient · Patient declined · Will address at next visit · Other (say why).

## Open questions for the owner or Dr Kintu

- Screen size of real clinic workstations (1366 x 768 assumed).
- Units: the test data uses mg/dL for creatinine; Ugandan labs often report µmol/L.
- Citation format: printed page, section heading, or both.
- Who finalizes: the same clinician, or can a supervisor co-sign?
