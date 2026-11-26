"use client";

import { useMutation, useQuery, type UseMutationResult } from "@tanstack/react-query";
import { use, useId, useState } from "react";

import { AppFrame, PaneContent, PaneHeader } from "@/components/frame/app-frame";
import { DayRail } from "@/components/frame/day-rail";
import { StatusChip, StatusShape, type VisitState } from "@/components/frame/status";
import { Tray, type TrayButton, type TrayProps } from "@/components/frame/tray";
import { api, errorText, unwrap, type Card, type DecisionOut, type Decisions, type PatientDetail, type VisitCheck } from "@/lib/api/client";
import { cn } from "@/lib/cn";
import { decisionsToSave, type Draft, type Reason } from "@/lib/decisions";
import { DISCLAIMER } from "@/lib/demo";
import { useRailEntries } from "@/lib/queries";

const NOTES_FORM = "clinical-notes";

export function VisitScreen({ params }: { params: Promise<{ patientId: string }> }) {
  const { patientId } = use(params);
  const patient = useQuery({
    queryKey: ["patient", patientId],
    queryFn: async () =>
      unwrap(await api.GET("/api/patients/{patient_id}", { params: { path: { patient_id: patientId } } })),
  });

  if (patient.data) return <Visit key={patient.data.patient_id} patient={patient.data} />;
  return (
    <Frame patientId={patientId} state="not_checked">
      <PaneContent>
        {patient.isPending && <p className="text-muted">Loading the record…</p>}
        {patient.isError && <p role="alert">{errorText(patient.error)}</p>}
      </PaneContent>
    </Frame>
  );
}

// Variables: run the AI review this time whatever the box says ("Run the AI review again").
type CheckMutation = UseMutationResult<VisitCheck, Error, { useAi?: boolean } | void>;

function Visit({ patient }: { patient: PatientDetail }) {
  const [note, setNote] = useState(String(patient.today_encounter.note ?? ""));
  const [useAi, setUseAi] = useState(false);
  const check: CheckMutation = useMutation({
    mutationFn: async (vars) =>
      unwrap(
        await api.POST("/api/patients/{patient_id}/visits", {
          params: { path: { patient_id: patient.patient_id } },
          body: { note, use_ai: vars?.useAi ?? useAi, include_plan: false },
        }),
      ),
  });

  const notesForm = (
    <form
      id={NOTES_FORM}
      className="flex max-w-3xl flex-col gap-3"
      onSubmit={(e) => {
        e.preventDefault();
        if (!check.isPending) check.mutate();
      }}
    >
      <label className="flex flex-col gap-2">
        <span className="text-20 font-semibold tracking-[-0.015em]">Clinical notes</span>
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          rows={6}
          maxLength={20000}
          className="rounded-btn border border-line-strong p-3 text-15 leading-[26px]"
        />
      </label>
      <label className="flex items-center gap-2 text-14 text-ink-2">
        <input type="checkbox" checked={useAi} onChange={(e) => setUseAi(e.target.checked)} /> AI review
      </label>
    </form>
  );

  // A new check starts the alert review afresh.
  return <VisitView key={check.data?.visit_id ?? "before"} patient={patient} check={check} notesForm={notesForm} />;
}

function VisitView({ patient, check, notesForm }: { patient: PatientDetail; check: CheckMutation; notesForm: React.ReactNode }) {
  const result = check.data;
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [saved, setSaved] = useState<Decisions | null>(null);
  const toSave = decisionsToSave(drafts);
  const save = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/visits/{visit_id}/decisions", {
          params: { path: { visit_id: result!.visit_id } },
          body: { decisions: toSave ?? [] },
        }),
      ),
    onSuccess: (reply) => {
      setSaved(reply);
      setDrafts({});
    },
  });
  const savedByAlert = new Map((saved?.decisions ?? []).map((d) => [d.alert_id, d]));
  const state: VisitState = check.isPending ? "checking" : (result?.status ?? "not_checked");

  return (
    <Frame
      patientId={patient.patient_id}
      state={state}
      disclaimer={result?.disclaimer}
      tray={
        <Tray
          {...trayFor({
            pending: check.isPending,
            result,
            savedIds: savedByAlert,
            canSave: Boolean(toSave) && !save.isPending && Boolean(result?.record_saved),
            onSave: () => save.mutate(),
            onRetryAi: () => check.mutate({ useAi: true }),
          })}
        />
      }
    >
      <PaneHeader title={patient.name} meta={patientMeta(patient)} aside={<StatusChip state={state} />} />
      <PaneContent>
        {notesForm}
        {check.isError && (
          <p role="alert" className="mt-4 text-red">
            {errorText(check.error)}
          </p>
        )}
        {result && (
          <Results
            check={result}
            drafts={drafts}
            savedByAlert={savedByAlert}
            finalizeNote={saved ? saved.finalize_note : result.finalize_note}
            saveError={save.isError ? errorText(save.error) : null}
            onDraft={(alertId, d) => setDrafts((all) => ({ ...all, [alertId]: d }))}
          />
        )}
      </PaneContent>
    </Frame>
  );
}

function Frame({
  patientId,
  state,
  disclaimer,
  tray,
  children,
}: {
  patientId: string;
  state: VisitState;
  disclaimer?: string;
  tray?: React.ReactNode;
  children: React.ReactNode;
}) {
  const rail = useRailEntries({ id: patientId, state });
  return (
    <AppFrame rail={<DayRail entries={rail} currentId={patientId} dimmed />} tray={tray} disclaimer={disclaimer ?? DISCLAIMER}>
      {children}
    </AppFrame>
  );
}

function patientMeta(p: PatientDetail): string {
  return [p.patient_id, `${p.age_years ?? "?"} ${p.sex}`.trim(), p.art_regimen_current.join("/")].filter(Boolean).join(" · ");
}

/**
 * The tray for where the visit is. The prompts before and during the checks are the design's
 * (S2, S3); the alert-review prompt is a stand-in until the one-alert-at-a-time screens (step 4).
 */
function trayFor({
  pending,
  result,
  savedIds,
  canSave,
  onSave,
  onRetryAi,
}: {
  pending: boolean;
  result: VisitCheck | undefined;
  savedIds: Map<string, DecisionOut>;
  canSave: boolean;
  onSave: () => void;
  onRetryAi: () => void;
}): TrayProps {
  const later = { plan: "todo", finalize: "todo" } as const;
  if (pending) {
    return { notes: "done", checks: "current", alerts: [], ...later, lead: "Checks running.", rest: "Results open by themselves.", status: <span /> };
  }
  if (!result) {
    return {
      notes: "current",
      checks: "todo",
      alerts: [],
      ...later,
      lead: "Clinical notes.",
      rest: "Write your plan, then run checks.",
      primary: { label: "Run checks", form: NOTES_FORM },
    };
  }
  const hasAlerts = result.cards.length > 0;
  const saveButton: TrayButton = { label: "Save decisions", onClick: onSave, disabled: !canSave };
  const retry: TrayButton = { label: "Run the AI review again", onClick: onRetryAi };
  const done = {
    notes: "done",
    checks: "done",
    alerts: result.cards.map((c) => (savedIds.has(c.extension.alert_id) ? "done" : "todo")),
    ...later,
  } as const;
  switch (result.ai_review) {
    // The design's S7a wording; running the review again can help when the model server failed.
    case "failed":
    case "unreadable":
      return {
        ...done,
        lead: "AI review failed.",
        rest: "Try again, or use rule checks only.",
        ...(hasAlerts ? { primary: saveButton, secondary: retry } : { primary: retry }),
      };
    case "cut_off":
    case "partly_read":
      return {
        ...done,
        lead: "AI review incomplete.",
        rest: hasAlerts ? "Review the alerts it read." : "Try again, or use rule checks only.",
        ...(hasAlerts ? { primary: saveButton, secondary: retry } : { primary: retry }),
      };
    // Running again won't help until the search model setting is fixed.
    case "search_unavailable":
      return {
        ...done,
        lead: "Guideline search unavailable.",
        rest: "Rule checks only.",
        primary: hasAlerts ? saveButton : undefined,
      };
    default:
      return {
        ...done,
        lead: hasAlerts ? "Alerts." : "Checks done.",
        rest: hasAlerts ? "Accept or override each one, then save." : undefined,
        primary: hasAlerts ? saveButton : undefined,
      };
  }
}

function Results({
  check,
  drafts,
  savedByAlert,
  finalizeNote,
  saveError,
  onDraft,
}: {
  check: VisitCheck;
  drafts: Record<string, Draft>;
  savedByAlert: Map<string, DecisionOut>;
  finalizeNote: string | null;
  saveError: string | null;
  onDraft: (alertId: string, d: Draft) => void;
}) {
  return (
    <section aria-label="Check results" className="mt-8 flex max-w-3xl flex-col gap-4">
      <h2 className="text-20 font-semibold tracking-[-0.015em]">Check results</h2>
      <Banners check={check} />
      {!check.record_saved && <p role="alert">This check could not be saved, so its alerts cannot be decided here.</p>}
      {check.cards.map((card) => (
        <AlertCard
          key={card.uuid}
          card={card}
          draft={drafts[card.extension.alert_id]}
          saved={savedByAlert.get(card.extension.alert_id)}
          onChange={(d) => onDraft(card.extension.alert_id, d)}
        />
      ))}
      {saveError && <p role="alert">{saveError}</p>}
      {finalizeNote && <p className="text-ink-2">{finalizeNote}</p>}
    </section>
  );
}

function AlertCard({
  card,
  draft,
  saved,
  onChange,
}: {
  card: Card;
  draft: Draft | undefined;
  saved: DecisionOut | undefined;
  onChange: (d: Draft) => void;
}) {
  const id = useId();
  const ext = card.extension;
  const current: Draft = draft ?? { action: "Acknowledge", reason: null, comment: "" };

  return (
    <article aria-labelledby={`${id}-heading`} className="flex flex-col gap-2 border-t border-line pt-4">
      <h3 id={`${id}-heading`} className="text-15 font-semibold">
        {ext.heading}
      </h3>
      <p>{card.detail}</p>
      {card.suggestions.map((s) => (
        <p key={s.uuid}>{s.label}</p>
      ))}
      {/* ext.explanation is left off: today it carries raw data and passage dumps, which the
          brief keeps off the main view (design question 9, for the backend). */}

      <h4 className="text-13 font-semibold text-ink-2">{ext.references_heading}</h4>
      <ul className="text-13 text-ink-2">
        {ext.references.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>

      <fieldset className="flex flex-wrap items-center gap-3">
        <legend className="sr-only">Decision</legend>
        {(["Acknowledge", "Override"] as const).map((action) => (
          <label key={action} className="flex items-center gap-1.5">
            <input
              type="radio"
              name={`${id}-action`}
              value={action}
              checked={draft?.action === action}
              onChange={() => onChange({ ...current, action })}
            />
            {action}
          </label>
        ))}
        {draft?.action === "Override" && (
          <>
            <label className="flex items-center gap-1.5">
              Override reason
              <select
                value={draft.reason ?? ""}
                onChange={(e) => onChange({ ...draft, reason: (e.target.value || null) as Reason | null })}
                className="rounded-chip border border-line-strong px-2 py-1"
              >
                <option value="">Choose a reason</option>
                {(card.overrideReasons ?? []).map((r) => (
                  <option key={r.code} value={r.display}>
                    {r.display}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex items-center gap-1.5">
              Comment
              <textarea
                value={draft.comment}
                onChange={(e) => onChange({ ...draft, comment: e.target.value })}
                maxLength={2000}
                rows={1}
                className="rounded-chip border border-line-strong px-2 py-1"
              />
            </label>
          </>
        )}
      </fieldset>
      {saved && (
        <p className="text-13 text-green">
          Saved: {saved.action}
          {saved.reason ? ` (${saved.reason})` : ""}
          {saved.comment ? `: ${saved.comment}` : ""}
        </p>
      )}
    </article>
  );
}

/**
 * The API's banners. When the AI review didn't end cleanly, its banner comes first
 * (screen_text.status_banners) and is shown in the Incomplete screen's (S7a) box, red or amber;
 * the overall result follows in S7a's result row. Owner's decision 5, 2026-11-26.
 */
function Banners({ check }: { check: VisitCheck }) {
  const aiProblem = !["ok", "not_run"].includes(check.ai_review);
  const [first, ...rest] = check.banners;
  const boxed = aiProblem && first && (first.level === "error" || first.level === "warning") ? first : null;
  const rows = boxed ? rest : check.banners;
  return (
    <>
      {boxed && (
        <div
          role="status"
          data-level={boxed.level}
          className={cn(
            "flex max-w-240 items-center gap-4.5 rounded-[14px] border-2 px-6 py-5.5",
            boxed.level === "error" ? "border-red bg-red-wash" : "border-amber bg-amber-wash",
          )}
        >
          <StatusShape state={boxed.level === "error" ? "RED" : "AMBER"} size={30} />
          <p className="text-16 font-medium text-ink">{boxed.text}</p>
        </div>
      )}
      {rows.map((b, i) => (
        <p key={i} role="status" data-level={b.level} className="flex h-15 max-w-240 items-center border-y border-line text-16 text-black">
          {b.text}
        </p>
      ))}
    </>
  );
}
