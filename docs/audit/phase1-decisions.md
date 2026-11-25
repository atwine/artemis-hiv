# Phase 1: decisions for the owner

The audit (`phase1-findings.tsv`, 225 findings) comes down to 40 root causes
(`phase1-groups.tsv`). Most can be fixed in only one sensible way. The 17 below can't: each
changes what a clinician sees, so the choice is yours. For each one there are options, what
each gets you and costs, and my pick with the reason that decides it.

Seven more decisions belong to later phases. They're listed at the end and can wait.

Reply with "your picks" to take all of mine, or name the ones you want differently.

---

## A. Which patient the results belong to

**D1 (G02). When the clinician switches to another patient, what happens to the results on
screen?**
- **Clear them.** Switching patients wipes the results; coming back means pressing Save again.
  You get no chance of showing or finalizing one patient's results under another. It costs one
  re-run when you go back.
- **Keep them per patient.** Each patient's last results come back when you return. It's
  handier, but it needs per-patient storage, which only arrives with D11's saved record.
- **My pick: clear them.** Showing the wrong patient's alerts is the worst fault in the audit,
  and clearing is the change that makes it impossible. Keeping results per patient can come
  later on top of D11.

## B. Alerts

**D2 (G04). How should the fixed-rule alerts and the AI alerts appear together?**
- **One list, each alert tagged "Rule check" or "AI review".** The clinician reviews one list,
  and the source of each alert is visible. When both flag the same problem (for example
  creatinine), it appears twice, once per source.
- **Two separate boxes**, rules first. The two sources are very clear apart, but the clinician
  has two lists to work through.
- **Merge them into one alert when they agree.** This gives the shortest list, but deciding
  that two alerts "agree" is itself guesswork. That kind of guessing is what deleted real
  alerts (D9).
- **My pick: one list with tags.** Nothing is ever dropped, the source stays visible, and no
  guesswork is involved.

**D3 (G05). When the AI screening fails or its reply can't be read, what then?**
- **Amber banner "AI review failed: only rule checks shown", finalize allowed.** The failure is
  recorded in the visit record (D11). The clinic isn't blocked when the server is down.
- **Block finalize until the AI review succeeds.** No visit is finalized without AI review, but
  a server outage stops the clinic.
- **My pick: amber banner, finalize allowed, failure recorded.** Today a failure looks exactly
  like a clean result. Making it visible fixes that without tying clinic work to the server.

**D4 (G21). An AI alert has no severity, or one that isn't low, moderate, high or critical.
What colour should it get?** And what about citations to passages the AI was never shown?
- **Severity: show "severity not given" and treat it as moderate (amber).** It's visible
  without being alarming.
- **Severity: treat it as high (red).** This is the cautious choice, but the model's wording
  ("severe", "medium") would turn screens red at random.
- **Citations: remove them, or keep them marked "not among the passages the AI was given".**
- **My pick: amber with "severity not given", and keep bad citations, marked.** Nothing gets
  hidden, and both problems stay visible to the clinician and to us.

**D5 (G22). Under each AI alert, which guideline passages should "References" list?**
- **Only the passages the AI was shown and cited.** References then mean what they say. Today
  81% of the listed passages were never shown to the AI.
- **Also related passages, in a separate labelled list.** You'd see more context, but at the
  cost of more to read and the risk of confusing it with real support.
- **My pick: only what the AI was shown and cited.**

**D6 (G20). The app merges alerts that look alike and cuts long ones. Keep doing that?**
- **Stop. Show the model's alerts as written, dropping only exact repeats.** That merging was
  built to tidy the old small model's repetition. With the 70B model it deleted real alerts
  (hepatitis B), merged a viral-load alert into a creatinine one, and cut "Hb 9.1 then 7.2" to
  "Hb 9.1".
- **Keep the merging.** You get shorter screens, but it keeps losing clinical content.
- **My pick: stop, and drop exact repeats only.**

## C. The patient record

**D7 (G06). Units for lab values entered in the add-case form.**
- **The clinician picks a unit for each value**, with the usual unit preselected (creatinine
  umol/L, viral load copies/mL). It costs one click per value. Unit mix-ups (1.4 mg/dL against
  140 umol/L) can't happen.
- **The app assumes one unit per test.** Entry is faster, but a value typed in the other unit
  is silently wrong. That's a 90-fold error for creatinine.
- **My pick: the clinician picks, with a default.** A silent unit error flips a kidney rule
  either way.

**D8 (G09). How should the ART regimen be entered?**
- **A pick-list of drugs** (TDF, 3TC, DTG and so on, plus common combinations such as TLD).
  The rules always recognise the drugs. It means changing the form, and the 3 saved custom
  cases need converting once.
- **Keep free text, and the app reads drug names out of it.** The form stays as it is, but
  typing variations will still slip through.
- **My pick: pick-list, plus a one-time conversion of the saved cases.** Free text is how the
  tenofovir rules missed P005, P006 and Kintu.

**D9 (G08). When a saved case is analysed again later, which date counts as the visit date?**
- **The date stored with the case.** The same case gives the same answer every time, and the
  baseline stays comparable.
- **Today's date.** Lab ages would always be counted from now, but every test patient's results
  would change from day to day.
- **My pick: the stored date**, with new cases getting today's date when they're created. The
  app would also work out each lab's age in days itself, instead of leaving the maths to the
  model, which got P001's age wrong in 3 of 3 runs.

**D10 (G11). What counts as today's clinician plan?**
- **The whole "Clinician's Assessment & Plan" box, sent to the AI under that label.** It's the
  smallest change, and it ends the false "no plan" alerts.
- **A separate Plan box**, with fields for orders and medication changes. That's cleaner input,
  but it's a screen redesign.
- **My pick: the whole box now, and the separate fields in the Phase 3 design.**

**D11 (G17). What should the saved visit record hold?**
- **Proposal:** the patient id, visit date, today's note, each alert (source, title, severity),
  the clinician's action (acknowledge or override), the override reason and comment, and the
  time. Also the model name, the app version, and whether AI review failed (D3).
- "Who" waits for logins in Phase 4. Until then the record is a local file, kept out of git.
- **"Other" as an override reason must come with a written comment:** yes or no?
- **My pick: the proposal, with a comment required for "Other".** An override with no reason
  can't be reviewed later.

## D. The management plan

**D12 (G13). The model gave no verdict on a plan item, or the clinician wrote no plan. What
should the screen say?**
- **Ask the model for a verdict on every item, and show "Not assessed" when it's missing.**
  When there is no clinician plan, show "No plan to compare" instead of "Matches your plan".
  Today "AGREE" appears for 36 of 44 items. The prompt itself tells the model to leave the
  verdict out when it agrees.
- **Hide the verdict line entirely.** That's simpler, but you lose the plan comparison, which
  is the point of the feature.
- **My pick: the first.** The screen never claims agreement nobody gave.

**D13 (G14). The regimen decision is something other than Switch, Hold or Continue, for
example "Uncertain" (P004, 3 of 3 runs). What badge should it get?**
- **A grey "Needs review" badge, with the model's own words.** Nothing is shown as green when
  it isn't.
- **No badge, only the text.**
- **My pick: grey "Needs review" with the model's words.**

**D14 (G15). The plan fails the app's own checks (17 of 21 baseline plans do) or can't be
produced. What then?**
- **Show it with a visible warning saying what failed.** Nothing is lost, and the clinician
  knows to treat it with care.
- **Hide it and show "Plan could not be produced".** It's the safest on screen, but it would
  hide most plans until the plan prompt is fixed.
- **My pick: show it with a warning, for now.** Once the D12 prompt fix lands, I'll recount how
  many plans fail. If it's few, hiding becomes the better rule and I'll ask again.

**D15 (G25). The "verification" step checks nothing, its answer is cut off mid-sentence, and
it's never shown. Delete it, or rebuild it?**
- **Delete it now.** You get less code and one fewer model call per visit. A real check can come
  back in the Phase 2B agentic loop.
- **Rebuild it now** to check the plan before it's shown. That's a design job, and it belongs
  with the retrieval revamp.
- **My pick: delete it now.**

**D16 (G24). When does a lab count as "rising" or "falling", and how is "<50" treated?**
- **A provisional rule, marked for the doctor to confirm.** Creatinine counts as rising when the
  last value is 20% or more above the first. Viral load counts as rising when it goes from
  suppressed (under 50) to 50 or more, or rises more than 3-fold. "<50" is stored as
  "suppressed", never dropped.
- **Leave trend labels out** until the doctor sets the rules.
- **My pick: the provisional rule, clearly marked "to confirm with the doctor".** Today any
  wobble counts as a trend and "<50" is thrown away, so even a rough rule is safer.

## E. Bring any retrieval faults forward from Phase 2B?

You ruled that retrieval faults go to Phase 2B. Two of them make today's output wrong in a
dangerous way and are small to fix.

**D17. Fix G29 and G30 now, in Phase 1?**
- **G29:** the text cleaner deletes anything between "<" and ">". So "VL < 50 … CD4 > 200"
  loses its numbers, and a South African chart now reads as if a viral load of 50 needs
  enhanced adherence support. 51 thresholds are lost.
- **G30:** if the guideline database fails to open, the backup keeps only the WHO file, with no
  warning.
- **Fix both now** (small changes, each with a test), and leave the rest of retrieval (G31 to
  G37) for 2B.
- **Leave both for 2B.** That keeps your rule exactly, but the app keeps reading damaged
  thresholds until then.
- **My pick: fix both now.** Both change medical meaning, both are a few lines, and neither
  affects the 2B design.

---

## Later phases (no answer needed now)

- **Phase 2B:**
  - G30's follow-up: stop with an error, or warn, when the index can't open.
  - G32: whether to search South African and WHO passages for Ugandan patients, and how
    citations name their source.
  - G33: the embedder fallback.
  - G34: how guideline text is stored (2B.7).
  - G36: printed page numbers.
- **Phase 2:**
  - G38: temperature 0, or judging each case over several runs.
  - G39: whether ARTEMIS flags problems outside HIV-drug safety, such as Kintu's blood pressure.
