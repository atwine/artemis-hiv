"use client";

import { useMutation, useQuery, type UseMutationResult } from "@tanstack/react-query";
import { use, useState } from "react";

import { AppFrame, PaneContent, PaneHeader } from "@/components/frame/app-frame";
import { DayRail } from "@/components/frame/day-rail";
import { StatusChip, type VisitState } from "@/components/frame/status";
import { Tray, type Step, type TrayButton, type TrayProps } from "@/components/frame/tray";
import { firstName, nextToReview } from "@/lib/alerts";
import { api, errorText, unwrap, type DecisionIn, type DecisionOut, type PatientDetail, type VisitCheck } from "@/lib/api/client";
import { acceptDecision, NEEDS_COMMENT, overrideDecision, type Reason } from "@/lib/decisions";
import { DISCLAIMER } from "@/lib/demo";
import { useRailEntries } from "@/lib/queries";
import { patientLine, possessive } from "@/lib/record";

import { AlertView } from "./alert-view";
import { OverrideView } from "./override-view";
import { RecordPanel } from "./record-panel";
import { Running, RunningTrayStatus } from "./running-view";
import { decisionWords, ResultsView } from "./results-view";

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
        {patient.isPending && <p className="text-muted-foreground">Loading the record…</p>}
        {patient.isError && <p role="alert">{errorText(patient.error)}</p>}
      </PaneContent>
    </Frame>
  );
}

// What one check sends: the note as written and whether the AI review runs ("Run the AI review
// again" sends it on whatever the box says).
type CheckRequest = { note: string; useAi: boolean };
type CheckMutation = UseMutationResult<VisitCheck, Error, CheckRequest>;

function Visit({ patient }: { patient: PatientDetail }) {
  const [note, setNote] = useState(String(patient.today_encounter.note ?? ""));
  const [useAi, setUseAi] = useState(false);
  const check: CheckMutation = useMutation({
    mutationFn: async (req: CheckRequest) =>
      unwrap(
        await api.POST("/api/patients/{patient_id}/visits", {
          params: { path: { patient_id: patient.patient_id } },
          body: { note: req.note, use_ai: req.useAi, include_plan: false },
        }),
      ),
  });

  // Before the checks (Paper FINAL S2): the record on the left, the notes box on the right.
  const notesForm = (
    <div className="flex min-h-full gap-10">
      <RecordPanel patient={patient} />
      <form
        id={NOTES_FORM}
        className="flex min-w-0 flex-1 flex-col gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (!check.isPending) check.mutate({ note, useAi });
        }}
      >
        <label htmlFor={`${NOTES_FORM}-text`} className="text-22 font-semibold tracking-[-0.015em] text-black">
          Clinical notes
        </label>
        <textarea
          id={`${NOTES_FORM}-text`}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          maxLength={20000}
          className="min-h-40 flex-1 resize-none rounded-[12px] border-2 border-line-strong bg-white px-5.5 py-5 text-16 leading-[26px] text-black focus:border-blue focus:shadow-[0_0_0_5px_var(--color-blue-wash)] focus:outline-none"
        />
        <p className="text-14 text-ink-2">
          The checks read this box against {possessive(patient.sex)} record. Write it as you normally would.
        </p>
        <label className="flex items-center gap-2 text-14 text-ink-2">
          <input type="checkbox" checked={useAi} onChange={(e) => setUseAi(e.target.checked)} /> AI review
        </label>
      </form>
    </div>
  );

  // A new check starts the review afresh.
  // The AI review this run: the box, unless "Run the AI review again" asked for it.
  const aiThisRun = check.variables?.useAi ?? useAi;
  return (
    <VisitView
      key={check.data?.visit_id ?? "before"}
      patient={patient}
      check={check}
      notesForm={notesForm}
      aiThisRun={aiThisRun}
      retryAi={() => check.mutate({ note, useAi: true })}
    />
  );
}

/** Which screen the pane shows. The results screen comes first after the checks (owner, 2026-11-26). */
type View = { name: "notes" } | { name: "results" } | { name: "alert"; i: number } | { name: "override"; i: number; other: boolean };

function VisitView({
  patient,
  check,
  notesForm,
  aiThisRun,
  retryAi,
}: {
  patient: PatientDetail;
  check: CheckMutation;
  notesForm: React.ReactNode;
  aiThisRun: boolean;
  retryAi: () => void;
}) {
  const result = check.data;
  const [view, setView] = useState<View>(result ? { name: "results" } : { name: "notes" });
  const [saved, setSaved] = useState<DecisionOut[]>([]);
  const [finalizeNote, setFinalizeNote] = useState<string | null>(result?.finalize_note ?? null);
  const [comment, setComment] = useState("");
  const save = useMutation({
    mutationFn: async (decision: DecisionIn) =>
      unwrap(
        await api.POST("/api/visits/{visit_id}/decisions", {
          params: { path: { visit_id: result!.visit_id } },
          body: { decisions: [decision] },
        }),
      ),
    onSuccess: (reply, decision) => {
      setSaved(reply.decisions);
      setFinalizeNote(reply.finalize_note);
      setComment("");
      // On to the next alert still to review, or back to the results when none is left.
      const ids = result!.cards.map((c) => c.extension.alert_id);
      const decided = new Set(reply.decisions.map((d) => d.alert_id));
      const next = nextToReview(ids, decided, ids.indexOf(decision.alert_id));
      setView(next === null ? { name: "results" } : { name: "alert", i: next });
    },
  });
  const savedByAlert = new Map(saved.map((d) => [d.alert_id, d]));
  const state: VisitState = check.isPending ? "checking" : (result?.status ?? "not_checked");
  const card = (view.name === "alert" || view.name === "override") && result ? result.cards[view.i] : undefined;

  const decide = (decision: DecisionIn | null) => {
    if (decision && !save.isPending) save.mutate(decision);
  };

  return (
    <Frame
      patientId={patient.patient_id}
      state={state}
      disclaimer={result?.disclaimer}
      tray={
        <Tray
          {...trayFor({
            view,
            pending: check.isPending,
            runningStatus: <RunningTrayStatus aiReview={aiThisRun} startedAt={check.submittedAt} />,
            result,
            savedByAlert,
            saving: save.isPending,
            patientName: patient.name,
            comment,
            go: (v) => {
              setComment("");
              setView(v);
            },
            accept: () => card && decide(acceptDecision(card.extension.alert_id)),
            saveOther: () => card && decide(overrideDecision(card.extension.alert_id, NEEDS_COMMENT, comment)),
            retryAi,
          })}
        />
      }
    >
      <PaneHeader title={patient.name} meta={patientLine(patient)} aside={<StatusChip state={state} />} />
      <PaneContent>
        {check.isPending && <Running patient={patient} aiReview={aiThisRun} startedAt={check.submittedAt} />}
        {!check.isPending && (view.name === "notes" || !result) && (
          <>
            {notesForm}
            {check.isError && (
              <p role="alert" className="mt-4 text-red">
                {errorText(check.error)}
              </p>
            )}
          </>
        )}
        {result && view.name === "results" && (
          <ResultsView
            check={result}
            patient={patient}
            noteSent={check.variables?.note ?? ""}
            savedByAlert={savedByAlert}
            finalizeNote={finalizeNote}
            saveError={save.isError ? errorText(save.error) : null}
            onOpen={(i) => setView({ name: "alert", i })}
          />
        )}
        {card && view.name === "alert" && <AlertView card={card} n={view.i + 1} />}
        {card && view.name === "override" && (
          <OverrideView
            card={card}
            n={view.i + 1}
            other={view.other}
            comment={comment}
            busy={save.isPending}
            onReason={(reason: Reason) =>
              reason === NEEDS_COMMENT
                ? setView({ ...view, other: true })
                : decide(overrideDecision(card.extension.alert_id, reason, ""))
            }
            onComment={setComment}
          />
        )}
        {card && save.isError && (
          <p role="alert" className="mt-4 text-red">
            {errorText(save.error)}
          </p>
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


/**
 * The tray for where the visit is. The prompts are the design's (S2, S3, S4, S4d, S7a); the
 * results-screen prompts are new with that screen (owner, 2026-11-26).
 */
function trayFor({
  view,
  pending,
  runningStatus,
  result,
  savedByAlert,
  saving,
  patientName,
  comment,
  go,
  accept,
  saveOther,
  retryAi,
}: {
  view: View;
  pending: boolean;
  runningStatus: React.ReactNode;
  result: VisitCheck | undefined;
  savedByAlert: Map<string, DecisionOut>;
  saving: boolean;
  patientName: string;
  comment: string;
  go: (v: View) => void;
  accept: () => void;
  saveOther: () => void;
  retryAi: () => void;
}): TrayProps {
  const later = { plan: "todo", finalize: "todo" } as const;
  if (pending) {
    return { notes: "done", checks: "current", alerts: [], ...later, lead: "Checks running.", rest: "Results open by themselves.", status: runningStatus };
  }
  const runChecks: TrayButton = { label: "Run checks", form: NOTES_FORM };
  if (!result) {
    return { notes: "current", checks: "todo", alerts: [], ...later, lead: "Clinical notes.", rest: "Write your plan, then run checks.", primary: runChecks };
  }

  const ids = result.cards.map((c) => c.extension.alert_id);
  const decided = new Set(savedByAlert.keys());
  const current = view.name === "alert" || view.name === "override" ? view.i : null;
  const steps = {
    notes: (view.name === "notes" ? "current" : "done") as Step,
    checks: (view.name === "results" ? "current" : "done") as Step,
    alerts: ids.map((id, i): Step => (i === current ? "current" : decided.has(id) ? "done" : "todo")),
    ...later,
    go: { notes: () => go({ name: "notes" }), checks: () => go({ name: "results" }), alert: (i: number) => go({ name: "alert", i }) },
  };
  const retry: TrayButton = { label: "Run the AI review again", onClick: retryAi };
  const of = (i: number) => `Alert ${i + 1} of ${ids.length}.`;

  if (view.name === "notes") {
    return { ...steps, lead: "Clinical notes.", rest: "Change the note, then run checks again.", primary: runChecks };
  }
  if (view.name === "alert") {
    const d = savedByAlert.get(ids[view.i]);
    return {
      ...steps,
      lead: of(view.i),
      rest: d
        ? d.action === "Acknowledge"
          ? "You accepted it."
          : `You overrode it: ${d.reason}.`
        : `Does it apply to ${firstName(patientName)} today?`,
      primary: { label: "Accept alert", onClick: accept, disabled: saving || !result.record_saved },
      secondary: { label: "Override", onClick: () => go({ name: "override", i: view.i, other: false }), disabled: saving || !result.record_saved },
    };
  }
  if (view.name === "override") {
    return {
      ...steps,
      lead: of(view.i),
      rest: view.other ? "Say why, then save the override." : "Tap a reason to save the override.",
      primary: view.other ? { label: "Save override", onClick: saveOther, disabled: saving || !comment.trim() } : undefined,
      secondary: { label: "Back to the alert", onClick: () => go({ name: "alert", i: view.i }) },
    };
  }

  // The results screen.
  const firstOpen = ids.findIndex((id) => !decided.has(id));
  const review: TrayButton | undefined = firstOpen >= 0 ? { label: `Review alert ${firstOpen + 1}`, onClick: () => go({ name: "alert", i: firstOpen }) } : undefined;
  const reviewed = ids.length > 0 && firstOpen < 0;
  switch (result.ai_review) {
    case "failed":
    case "unreadable":
      return { ...steps, lead: "AI review failed.", rest: "Try again, or use rule checks only.", ...(review ? { primary: review, secondary: retry } : { primary: retry }) };
    case "cut_off":
    case "partly_read":
      return {
        ...steps,
        lead: "AI review incomplete.",
        rest: ids.length ? "Review the alerts it read." : "Try again, or use rule checks only.",
        ...(review ? { primary: review, secondary: retry } : { primary: retry }),
      };
    case "search_unavailable":
      return { ...steps, lead: "Guideline search unavailable.", rest: "Rule checks only.", primary: review };
    default:
      if (!ids.length) return { ...steps, lead: "Checks done.", rest: "No alerts to review." };
      return reviewed
        ? { ...steps, lead: "Every alert has your answer.", rest: savedSummary(savedByAlert) }
        : { ...steps, lead: `${ids.length} ${ids.length === 1 ? "alert" : "alerts"} to review.`, rest: "Accept or override each one.", primary: review };
  }
}

function savedSummary(saved: Map<string, DecisionOut>): string {
  const words = [...saved.values()].map(decisionWords);
  const accepted = words.filter((w) => w === "Accepted").length;
  const overridden = words.length - accepted;
  return [accepted && `${accepted} accepted`, overridden && `${overridden} overridden`].filter(Boolean).join(", ") + ".";
}
