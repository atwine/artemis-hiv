# Clutter audit, round 1 (2026-11-26)

Scope: the busiest screen of each direction as it stood mid-build (S4 results and review for
01, 02, 03, 05; S5 plan comparison for 04, whose S4 wasn't built yet), checked against the
avatar checklist and the screen budget in `brief.md`. A full screen-by-screen audit follows
once the builders have split the screens. Evidence: Paper screenshots of those frames, kept
on each page as "Before declutter".

Verdict for all five: well made, but every one breaks the budget on its core screen. The
same four habits cause most of it.

## The four habits behind the clutter

1. **The same thing shown twice.** 01 shows alert 3 in the middle pane and again in the right
   rail. 04 shows the five plan items as a timeline and again as a table. 02 repeats every
   alert title in the step list and in the heading.
2. **Several decisions open at once.** 03 and 05 put Accept and Override on two or three
   alerts at the same time; 05 has two alerts fully expanded plus an override form.
3. **Always-on panels.** 01 keeps the 7-patient queue, four tabs, header counters and a
   footer on the review screen; 02 keeps an 8-step list with two lines per step; 03 runs three
   reading columns side by side.
4. **Too many labels per alert.** Most alert cards carry 4 to 5 tags (severity, kind, source,
   "3 of 5", time) in 11 to 12px text, plus keyboard badges (A, O, 0, 1 to 6) in 01 and 05.

## Per direction

| Direction | Blocks in the working area (budget 3) | Decisions open (budget 1) | Shown twice | Biggest cut |
|---|---|---|---|---|
| 01 Triage Board | about 9 (queue, header counts, tabs, record side, guideline side, conclusion bar, alert card, reason list, more alerts, reviewed list, Finalize) | 1, plus "Review next" | alert 3 (middle and rail); patient counts (header and queue) | Queue off the review screen; the rail and the middle pane become one alert view |
| 02 Guided Review | about 5 (step list, record panel, guideline panel, action, reason panel) | 1 | alert titles (steps and heading) | Step list shows numbers and status only; the reason picker replaces the buttons instead of sitting beside them |
| 03 Evidence Desk | about 7 (alert list with inline reasons, reviewed list, claim text, 4 record cards, connector lines, guideline page, chip bar) | 3 | alert 3 (list and desk) | Alert list becomes its own screen; the desk shows one alert, one value, one guideline row |
| 04 Patient Timeline (plan) | about 4 (two-futures chart, table, monitoring panel, counselling) | n/a | the five plan items (chart and table) | Keep the two futures; move the table one click away |
| 05 Note Co-pilot | about 6 (note, reviewed strip, two full alert cards, reason form, NSAID strip) | 2 | ibuprofen problem (alert and the NSAID strip) | One expanded margin note at a time; reviewed notes shrink to a one-line stub |

## What changes next

Each direction keeps its idea and splits its busy screens into smaller ones (for example: a
visit summary with five one-line alerts, one screen per alert, a reason step, a separate
record screen, the guideline page on its own). The flow map on each cover is redrawn to
show the new steps. Then an independent check runs every screen against the budget.
