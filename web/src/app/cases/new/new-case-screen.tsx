"use client";

// Adding a patient case (Paper FINAL S8a "patient and medicines", S8b "labs and clinical notes").
// The form is kept as a draft in this browser while typing and comes back after a reload; Save
// case or Cancel clears it (owner, 2026-11-26). Saving books the case at its time on its visit
// date, in the same save (POST /api/patients). The backend checks everything again and its
// reasons are shown as sent.
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { AppFrame, PaneContent, PaneHeader } from "@/components/frame/app-frame";
import { DayRail } from "@/components/frame/day-rail";
import { FormTray } from "@/components/frame/tray";
import { api, errorText, type PatientDetail } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";
import { todayIso } from "@/lib/dates";
import { DISCLAIMER } from "@/lib/demo";
import {
  addsTo,
  blankLab,
  blankPast,
  DRAFT_KEY,
  emptyDraft,
  formErrors,
  parseDraft,
  partOneProblems,
  pickLists,
  toggleDrug,
  toNewCase,
  unaddedMedicine,
  withShortcut,
  type CaseDraft,
  type LabRow,
  type PastRegimen,
  type SavedDraft,
} from "@/lib/new-case";
import { useFormChoices, useRailEntries } from "@/lib/queries";
import { patientLine } from "@/lib/record";
import { cn } from "@/lib/utils";

type FormChoices = components["schemas"]["FormChoices"];

// The draft in this browser's storage. Storage can be blocked (some private windows): the form
// then works without a draft instead of failing.
function readDraft(): SavedDraft | null {
  try {
    return parseDraft(window.localStorage.getItem(DRAFT_KEY));
  } catch {
    return null;
  }
}

function writeDraft(saved: SavedDraft | null) {
  try {
    if (saved) window.localStorage.setItem(DRAFT_KEY, JSON.stringify(saved));
    else window.localStorage.removeItem(DRAFT_KEY);
  } catch {
    // Nothing kept: the form still works.
  }
}

/** The backend refused the case: its reasons, one per line. */
class CaseRefused extends Error {
  constructor(readonly reasons: string[]) {
    super(reasons.join(" "));
  }
}

export function NewCaseScreen() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const choices = useFormChoices();
  const rail = useRailEntries();
  const [today] = useState(todayIso);
  // This screen is drawn in the browser only (page.tsx), so the draft can be read as it starts.
  const [form, setForm] = useState<SavedDraft>(() => readDraft() ?? { part: 1, draft: emptyDraft(today) });
  const [problems, setProblems] = useState<string[]>([]);
  const [medicine, setMedicine] = useState(""); // the "Other medicine" box, before it is added
  const finished = useRef(false);

  useEffect(() => {
    if (!finished.current) writeDraft(form);
  }, [form]);

  const save = useMutation({
    mutationFn: async (draft: CaseDraft): Promise<PatientDetail> => {
      const reply = await api.POST("/api/patients", { body: toNewCase(draft) });
      if (reply.data) return reply.data;
      throw new CaseRefused(formErrors((reply.error as { detail?: unknown } | undefined)?.detail));
    },
    onSuccess: (patient) => {
      finished.current = true;
      writeDraft(null);
      void queryClient.invalidateQueries({ queryKey: ["clinic-day"] });
      router.push(`/patients/${encodeURIComponent(patient.patient_id)}`); // its new visit (owner, 2026-11-27)
    },
    onError: (err) => setProblems(err instanceof CaseRefused ? err.reasons : [errorText(err)]),
  });

  const cancel = () => {
    finished.current = true;
    writeDraft(null);
    router.push("/");
  };

  const edit = (change: Partial<CaseDraft>) => setForm((f) => ({ ...f, draft: { ...f.draft, ...change } }));
  const { draft, part } = form;
  // On to part 2 once part 1 is complete; previous-ART rows left blank go, so the rows on screen
  // are the rows the backend numbers in its reasons.
  const next = () => {
    const unadded = unaddedMedicine(medicine);
    const left = unadded ? [...partOneProblems(draft), unadded] : partOneProblems(draft);
    setProblems(left);
    if (!left.length) setForm((f) => ({ part: 2, draft: { ...f.draft, previousArt: f.draft.previousArt.filter((a) => !blankPast(a)) } }));
  };
  // Back to part 1 keeps any reasons the backend gave: most are about part 1's boxes.
  const back = () => setForm((f) => ({ ...f, part: 1 }));

  const who = draft.name.trim() || draft.patientId.trim() || "New patient";
  const header =
    part === 1 ? (
      <PaneHeader title="New patient case" meta="Part 1 of 2 · patient and medicines" aside={<DraftChip />} back={<HeaderButton onClick={cancel}>Cancel</HeaderButton>} />
    ) : (
      <PaneHeader
        title={who}
        meta={`${patientLine({ patient_id: draft.patientId.trim(), age_years: draft.age ? Number(draft.age) : null, sex: draft.sex, art_regimen_current: draft.drugs })} · new case, part 2 of 2`}
        aside={<DraftChip />}
        back={<HeaderButton onClick={back}>← Part 1</HeaderButton>}
      />
    );

  const tray =
    part === 1 ? (
      <FormTray label="New case steps" text="New patient case · Part 1 of 2. Saved as a draft as you type." primary={{ label: "Next: labs and clinical notes", onClick: next }} />
    ) : (
      <FormTray
        label="New case steps"
        text={`New patient case · Part 2 of 2. ${addsTo(draft.name, draft.visitDate, today)}`}
        primary={{ label: save.isPending ? "Saving…" : "Save case", disabled: save.isPending, onClick: () => save.mutate(draft) }}
      />
    );

  return (
    <AppFrame rail={<DayRail entries={rail} dimmed />} tray={tray} disclaimer={DISCLAIMER}>
      {header}
      <PaneContent>
        {problems.length > 0 && (
          <div role="alert" className="mb-5 rounded-btn bg-red-wash px-4 py-3 text-15 text-black">
            <ul className="flex flex-col gap-1">
              {problems.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          </div>
        )}
        {choices.isError && <p role="alert">{errorText(choices.error)}</p>}
        {choices.data && (part === 1 ? <PartOne draft={draft} choices={choices.data} edit={edit} medicine={medicine} setMedicine={setMedicine} /> : <PartTwo draft={draft} choices={choices.data} edit={edit} />)}
      </PaneContent>
    </AppFrame>
  );
}

function DraftChip() {
  return <span className="flex h-7 items-center rounded-chip bg-fill px-2.5 text-13 font-semibold tracking-[0.02em] text-ink-2">DRAFT</span>;
}

function HeaderButton({ onClick, children }: { onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" onClick={onClick} className="cursor-pointer text-14 font-medium text-ink-2">
      {children}
    </button>
  );
}

const BOX = "h-10.5 rounded-md border border-line-strong bg-white px-3 text-15 text-black placeholder:text-muted-foreground focus:border-2 focus:border-blue focus:px-[11px] focus:outline-none";
const SELECT = cn(BOX, "appearance-none bg-[length:10px] bg-[right_12px_center] bg-no-repeat pr-8");
// The design's "▾" in the muted colour, drawn so the native select keeps its own keyboard use.
const CARET = { backgroundImage: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 10 6'%3E%3Cpath d='M0 0h10L5 6z' fill='%23667080'/%3E%3C/svg%3E\")" };

function Field({ label, htmlFor, className, children }: { label: string; htmlFor: string; className?: string; children: React.ReactNode }) {
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <label htmlFor={htmlFor} className="text-14 font-medium text-ink-2">
        {label}
      </label>
      {children}
    </div>
  );
}

type EditProps = { draft: CaseDraft; choices: FormChoices; edit: (change: Partial<CaseDraft>) => void };

function PartOne({ draft, choices, edit, medicine, setMedicine }: EditProps & { medicine: string; setMedicine: (text: string) => void }) {
  const { drugs, shortcuts } = pickLists(choices.art_regimens);
  const pronoun = draft.sex === "F" ? "she takes" : draft.sex === "M" ? "he takes" : "the patient takes";
  const addMedicine = () => {
    if (!medicine.trim()) return;
    edit({ medicines: [...draft.medicines, medicine.trim()] });
    setMedicine("");
  };
  const past = draft.previousArt;
  const setPast = (i: number, change: Partial<PastRegimen>) => edit({ previousArt: past.map((a, j) => (j === i ? { ...a, ...change } : a)) });

  return (
    <div className="flex flex-col gap-6">
      <div className="flex gap-3.5">
        <Field label="ID" htmlFor="case-id" className="w-27.5 shrink-0">
          <input id="case-id" className={BOX} value={draft.patientId} maxLength={40} autoComplete="off" onChange={(e) => edit({ patientId: e.target.value })} />
        </Field>
        <Field label="Name" htmlFor="case-name" className="min-w-0 flex-1">
          <input id="case-name" className={BOX} value={draft.name} maxLength={200} autoComplete="off" onChange={(e) => edit({ name: e.target.value })} />
        </Field>
        <Field label="Age" htmlFor="case-age" className="w-20 shrink-0">
          <input id="case-age" className={BOX} value={draft.age} inputMode="numeric" maxLength={3} onChange={(e) => edit({ age: e.target.value.replace(/\D/g, "") })} />
        </Field>
        <Field label="Sex" htmlFor="case-sex" className="w-30 shrink-0">
          <select id="case-sex" className={SELECT} style={CARET} value={draft.sex} onChange={(e) => edit({ sex: e.target.value as CaseDraft["sex"] })}>
            <option value="">Not given</option>
            <option value="F">Female</option>
            <option value="M">Male</option>
          </select>
        </Field>
        <Field label="Visit date" htmlFor="case-date" className="w-37.5 shrink-0">
          <input id="case-date" type="date" className={BOX} value={draft.visitDate} onChange={(e) => edit({ visitDate: e.target.value })} />
        </Field>
        <Field label="Time" htmlFor="case-time" className="w-24 shrink-0">
          <input id="case-time" className={BOX} value={draft.time} placeholder="09:30" inputMode="numeric" maxLength={5} autoComplete="off" onChange={(e) => edit({ time: e.target.value })} />
        </Field>
        <Field label="Visit type" htmlFor="case-type" className="w-47.5 shrink-0">
          <select id="case-type" className={SELECT} style={CARET} value={draft.visitType} onChange={(e) => edit({ visitType: e.target.value })}>
            <option value="">Not given</option>
            {choices.visit_types.map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
        </Field>
      </div>

      <section aria-labelledby="regimen-heading" className="flex flex-col gap-2.5">
        <div className="flex items-baseline gap-3">
          <h2 id="regimen-heading" className="text-18 font-semibold text-black">
            Current ART regimen
          </h2>
          <p className="text-14 text-ink-2">
            Tap each drug {pronoun}.{draft.drugs.length > 0 && ` Picked: ${draft.drugs.join(", ")}.`}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {drugs.map((d) => (
            <DrugChip key={d} drug={d} picked={draft.drugs.includes(d)} onClick={() => edit({ drugs: toggleDrug(draft.drugs, d) })} />
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-2.5">
          <span className="text-14 text-muted-foreground">Shortcut:</span>
          {shortcuts.map((s) => (
            <button
              key={s.choice}
              type="button"
              onClick={() => edit({ drugs: withShortcut(draft.drugs, s.drugs) })}
              className="flex h-8 cursor-pointer items-center rounded-chip bg-mint px-3 text-14 font-semibold text-green"
            >
              {s.choice} = {s.drugs.join("/")}
            </button>
          ))}
        </div>
      </section>

      <section aria-labelledby="medicines-heading" className="flex flex-col gap-2.5">
        <h2 id="medicines-heading" className="text-18 font-semibold text-black">
          Other medicines and previous ART
        </h2>
        {draft.medicines.length > 0 && (
          <ul aria-label="Other medicines" className="flex flex-col">
            {draft.medicines.map((m, i) => (
              <li key={`${i}-${m}`} className="flex h-10 items-center gap-3 border-b border-line text-15">
                <span className="w-27.5 shrink-0 text-14 font-medium text-ink-2">Medicine</span>
                <span className="flex-1 text-black">{m}</span>
                <button
                  type="button"
                  aria-label={`Remove ${m}`}
                  onClick={() => edit({ medicines: draft.medicines.filter((_, j) => j !== i) })}
                  className="cursor-pointer font-medium text-ink-2"
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
        )}
        {past.length > 0 && (
          <ul aria-label="Previous ART" className="flex flex-col">
            {past.map((a, i) => {
              const n = i + 1;
              return (
                <li key={i} className="flex items-center gap-3 border-b border-line py-2.5">
                  <span className="w-27.5 shrink-0 text-14 font-medium text-ink-2">Previous ART</span>
                  <div role="group" aria-label={`Previous ART ${n} drugs`} className="flex min-w-0 flex-1 flex-wrap gap-1.5">
                    {drugs.map((d) => (
                      <DrugChip key={d} small drug={d} picked={a.drugs.includes(d)} onClick={() => setPast(i, { drugs: toggleDrug(a.drugs, d) })} />
                    ))}
                  </div>
                  <span aria-hidden className="text-14 text-ink-2">
                    From
                  </span>
                  <input aria-label={`Previous ART ${n} from`} type="date" className={cn(BOX, "w-36 shrink-0 px-2.5 focus:px-[9px]")} value={a.start} onChange={(e) => setPast(i, { start: e.target.value })} />
                  <span aria-hidden className="text-14 text-ink-2">
                    to
                  </span>
                  <input aria-label={`Previous ART ${n} to`} type="date" className={cn(BOX, "w-36 shrink-0 px-2.5 focus:px-[9px]")} value={a.end} onChange={(e) => setPast(i, { end: e.target.value })} />
                  <button
                    type="button"
                    aria-label={`Remove previous ART ${n}`}
                    onClick={() => edit({ previousArt: past.filter((_, j) => j !== i) })}
                    className="cursor-pointer text-15 font-medium text-ink-2"
                  >
                    Remove
                  </button>
                </li>
              );
            })}
          </ul>
        )}
        <div className="flex gap-3">
          <input
            aria-label="Other medicine"
            className={cn(BOX, "min-w-0 flex-1")}
            placeholder="Name, dose, how often"
            value={medicine}
            maxLength={200}
            onChange={(e) => setMedicine(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                addMedicine();
              }
            }}
          />
          <button type="button" onClick={addMedicine} className="h-10.5 cursor-pointer rounded-md border border-dashed border-line-strong px-4 text-15 font-medium text-black">
            <span aria-hidden>+ </span>Add medicine
          </button>
          <button
            type="button"
            onClick={() => edit({ previousArt: [...past, { drugs: [], start: "", end: "" }] })}
            className="h-10.5 cursor-pointer rounded-md border border-dashed border-line-strong px-4 text-15 font-medium text-black"
          >
            <span aria-hidden>+ </span>Add previous ART, with dates
          </button>
        </div>
      </section>
    </div>
  );
}

/** A drug to tap; small in a previous-ART row (S8a). */
function DrugChip({ drug, picked, small, onClick }: { drug: string; picked: boolean; small?: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      aria-pressed={picked}
      onClick={onClick}
      className={cn(
        "flex cursor-pointer items-center rounded-full",
        small ? "h-8 px-3 text-14" : "h-10 px-4 text-15",
        picked ? "bg-button font-semibold text-white" : "border border-line-strong text-black",
      )}
    >
      {picked && <span aria-hidden>✓&nbsp;</span>}
      {drug}
    </button>
  );
}

const EMPTY_LAB: LabRow = { test: "", date: "", value: "", unit: "" };

// Today's intake as three short boxes above the note (owner, 2026-11-27).
const INTAKE = [
  { key: "complaints", id: "case-complaints", label: "Complaints" },
  { key: "exam", id: "case-exam", label: "Exam findings" },
  { key: "history", id: "case-history", label: "History before today" },
] as const;

function PartTwo({ draft, choices, edit }: EditProps) {
  const rows = draft.labs.length ? draft.labs : [EMPTY_LAB];
  const setRow = (i: number, change: Partial<LabRow>) => edit({ labs: rows.map((r, j) => (j === i ? { ...r, ...change } : r)) });
  const unitsOf = (test: string) => choices.lab_tests.find((t) => t.test === test)?.units ?? [];
  const pickTest = (i: number, test: string) => {
    // A new test brings its usual unit; clearing the test clears the row.
    setRow(i, test ? { test, unit: unitsOf(test)[0] ?? "" } : EMPTY_LAB);
  };

  return (
    <div className="flex gap-9">
      <section aria-labelledby="labs-heading" className="flex w-150 shrink-0 flex-col gap-2.5">
        <div className="flex items-baseline gap-3">
          <h2 id="labs-heading" className="text-18 font-semibold text-black">
            Lab results
          </h2>
          <p className="text-14 text-ink-2">One row per result, always with a unit.</p>
        </div>
        <div role="table" aria-label="Lab results" className="flex flex-col">
          <div role="row" className="flex h-7.5 items-center gap-2 text-13 font-semibold tracking-[0.05em] text-muted-foreground">
            <span role="columnheader" className="w-47.5 shrink-0">TEST</span>
            <span role="columnheader" className="w-32.5 shrink-0">DATE</span>
            <span role="columnheader" className="w-25 shrink-0">VALUE</span>
            <span role="columnheader" className="flex-1">UNIT</span>
          </div>
          {rows.map((r, i) => {
            const n = i + 1;
            const units = unitsOf(r.test);
            const cell = cn(BOX, "h-10 px-2.5 focus:px-[9px]", blankLab(r) && "border-dashed");
            return (
              <div role="row" key={i} className="flex gap-2 py-1">
                <span role="cell" className="flex w-47.5 shrink-0">
                  <select aria-label={`Result ${n} test`} className={cn(cell, "w-full appearance-none bg-[length:10px] bg-[right_10px_center] bg-no-repeat", !r.test && "text-muted-foreground")} style={CARET} value={r.test} onChange={(e) => pickTest(i, e.target.value)}>
                    <option value="">Pick a test</option>
                    {choices.lab_tests.map((t) => (
                      <option key={t.test} value={t.test}>
                        {t.label}
                      </option>
                    ))}
                  </select>
                </span>
                <span role="cell" className="flex w-32.5 shrink-0">
                  <input aria-label={`Result ${n} date`} type="date" className={cn(cell, "w-full")} value={r.date} onChange={(e) => setRow(i, { date: e.target.value })} />
                </span>
                <span role="cell" className="flex w-25 shrink-0">
                  <input aria-label={`Result ${n} value`} className={cn(cell, "w-full")} placeholder="Value" value={r.value} maxLength={40} onChange={(e) => setRow(i, { value: e.target.value })} />
                </span>
                <span role="cell" className="flex min-w-0 flex-1">
                  <select
                    aria-label={`Result ${n} unit`}
                    className={cn(cell, "w-full min-w-0 appearance-none bg-[length:10px] bg-[right_10px_center] bg-no-repeat", !r.unit && "text-muted-foreground")}
                    style={r.test ? CARET : undefined}
                    value={r.unit}
                    disabled={!r.test}
                    onChange={(e) => setRow(i, { unit: e.target.value })}
                  >
                    {!r.test && <option value="">Unit follows test</option>}
                    {units.map((u) => (
                      <option key={u}>{u}</option>
                    ))}
                  </select>
                </span>
              </div>
            );
          })}
        </div>
        <button type="button" onClick={() => edit({ labs: [...rows, EMPTY_LAB] })} className="cursor-pointer self-start text-15 font-semibold text-blue">
          <span aria-hidden>+ </span>Add result
        </button>
      </section>

      <div className="flex min-w-0 flex-1 flex-col gap-3.5">
        <div className="flex gap-3">
          {INTAKE.map(({ key, id, label }) => (
            <Field key={key} label={label} htmlFor={id} className="min-w-0 flex-1">
              <input id={id} className={BOX} value={draft[key]} placeholder="Optional" maxLength={5000} autoComplete="off" onChange={(e) => edit({ [key]: e.target.value })} />
            </Field>
          ))}
        </div>
        <label htmlFor="case-note" className="text-20 font-semibold tracking-[-0.015em] text-black">
          Clinical notes
        </label>
        <textarea
          id="case-note"
          value={draft.note}
          maxLength={20000}
          placeholder="Write it as you normally would. The checks read this box."
          onChange={(e) => edit({ note: e.target.value })}
          className="min-h-60 flex-1 resize-none rounded-[12px] border-2 border-line-strong bg-white px-4.5 py-4 text-16 leading-6 text-black placeholder:text-muted-foreground focus:border-blue focus:shadow-[0_0_0_5px_var(--color-blue-wash)] focus:outline-none"
        />
      </div>
    </div>
  );
}
