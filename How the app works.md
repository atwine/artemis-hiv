# How the app works

This explains how to use **ARTEMIS-HIV** for anyone who isn't technical: clinicians, programme
staff, researchers. How to install and start it is in `README.md`.

## What this app is for

The app helps you **notice important clinical follow-ups** during an HIV care visit. For each
patient it:

- checks the patient's record and today's note for situations that need attention, with fixed
  safety rules and an AI review;
- shows the passages from the **Ugandan HIV guidelines** behind each alert, with their pages;
- explains in a sentence or two why each alert was raised;
- on request, writes the AI's management plan and compares it with yours.

Important:

- This is **decision support only**. It does not replace clinical judgement or the official
  guidelines.
- The patients in this demo are **made up**. You can safely explore.

## A clinic day, step by step

### 1. The day board

The app opens on the clinic day: each booked patient in time order, with where their visit
stands (waiting, needs you, done) and how many patients are still left in red. The arrows step
to the clinic days before and after.

**Add a case** adds a made-up patient: their details, medicines, lab results, earlier ART and
today's note, booked at a time on their visit date.

### 2. Open a patient and write today's note

The patient's record is on the left: medicines, earlier ART, lab results with their dates and
units, and earlier notes. Write today's note on the right as you normally would, including your
plan.

### 3. Run the checks

**Run checks** reads the record and your note:

- The **rule checks** always run. They catch fixed situations, such as an overdue creatinine on
  tenofovir.
- The **AI review** runs when a model server is set up. It may only raise problems the Ugandan
  guidelines support, and it cites the passages it read.

Each alert says which of the two raised it, how serious it is, the patient values it is about,
the key guideline sentence, and the passages behind it.

If the AI review failed or was cut short, a banner says so: a missing AI review never looks like
a clean result. If the guideline search isn't working, a red banner says the AI review is off
and only the rule checks ran.

Every check is saved, so you can come back to a visit later without running the AI again.

### 4. Acknowledge or override each alert

For each alert, choose:

- **Acknowledge**: you agree it matters and have noted it.
- **Override**: it doesn't apply to this patient, or you choose not to act on it now. Pick a
  reason:
  - Already done, not documented
  - Test not available here
  - Not right for this patient
  - Patient declined
  - Will address at next visit
  - Other (say why), which needs a comment

### 5. Compare plans

**Compare plans** asks the AI for its management plan for this visit: whether to switch, hold or
continue the ART regimen, each problem with what it suggests, monitoring and counselling. Each
item says how it compares with the plan in your note ("Matches your plan", "Differs from your
plan", "Partly in your plan", "Not in your plan"), or "No plan to compare" when your note had
none. A plan that failed the app's own checks is shown with a warning. Pressing it again shows
the same plan without asking the AI again, unless the last one failed or was flagged.

(This screen is being built in the website; the rest of the app is ready for it.)

### 6. Finalize

**Finalize** stays disabled until every alert is acknowledged or overridden with a reason. It
then closes the visit. If you change a decision afterwards, the visit opens again until you
finalize it once more. Nothing is ever deleted: each decision and each Finalize is kept.

## What the colours mean

- **Red**: at least one high or critical alert.
- **Amber**: alerts, none of them high or critical.
- **Green**: no alerts, and the AI review finished cleanly (or was switched off).
- **Incomplete**: no alerts, but the AI review didn't finish cleanly, so the visit is never shown
  as green.

## Troubleshooting

### "Guideline search unavailable"

The app couldn't load its guideline search. The rule checks still run; the AI review and Compare
plans wait until it works again. Ask the technical team (`README.md`, "Troubleshooting").

### The first check of the day is slow

The first check loads the guideline search, which can take a minute. Later checks are quicker.

### "No AI model server is set up"

The AI review and Compare plans need a model server; the technical team sets it up. The rule
checks still work without it.

### "Too many visit checks"

Checks and plans together are limited to 6 a minute, so a stuck page can't run up the model's
cost. Wait a moment and try again.

## Privacy and safety notes

- The demo patients are made up, and the app only answers pages on this laptop.
- Treat every output as **supporting information**, not a final decision.
- Always confirm with the official guidelines and your clinical judgement.
