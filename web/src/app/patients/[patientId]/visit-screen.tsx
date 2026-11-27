"use client";

import { useMutation, useQuery, useQueryClient, type QueryClient, type UseMutationResult } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { use, useState } from "react";

import { AppFrame, PaneContent, PaneHeader } from "@/components/frame/app-frame";
import { DayRail } from "@/components/frame/day-rail";
import { StatusChip, type VisitState } from "@/components/frame/status";
import { Tray, type Step, type TrayButton, type TrayProps } from "@/components/frame/tray";
import { firstName, nextToReview } from "@/lib/alerts";
import { api, errorText, unwrap, type DecisionIn, type DecisionOut, type PatientDetail, type SavedVisit, type VisitCheck } from "@/lib/api/client";
import { acceptDecision, NEEDS_COMMENT, overrideDecision, type Reason } from "@/lib/decisions";
import { DISCLAIMER } from "@/lib/demo";
import { planState, type ManagementPlan, type PlanState } from "@/lib/plan";
import type { DayAppointment } from "@/lib/day";
import { useClinicDay, useRailEntries, visitHref } from "@/lib/queries";
import { nextPatient } from "@/lib/visit";
import { patientLine, possessive } from "@/lib/record";

import { AlertView } from "./alert-view";
import { FinalizeView, RecordView } from "./finalize-view";
import { OverrideView } from "./override-view";
import { PlanView } from "./plan-view";
import { RecordPanel } from "./record-panel";
import { Running, RunningTrayStatus } from "./running-view";
import { decisionWords, ResultsView } from "./results-view";

const NOTES_FORM = "clinical-notes";

export function VisitScreen({ params }: { params: Promise<{ patientId: string }> }) {
  const { patientId } = use(params);
  // A saved visit to reopen (from the clinic day): shown as saved, with no new check (S1 -> S4).
  const visitId = useSearchParams().get("visit");
  // A visit this screen just created: the address then names it, but the screen carries on as it is.
  const [created, setCreated] = useState<string | null>(null);
  const patient = useQuery({
    queryKey: ["patient", patientId],
    queryFn: async () =>
      unwrap(await api.GET("/api/patients/{patient_id}", { params: { path: { patient_id: patientId } } })),
  });
  const reopened = useQuery({
    queryKey: ["visit", visitId],
    queryFn: async () => unwrap(await api.GET("/api/visits/{visit_id}", { params: { path: { visit_id: visitId! } } })),
    enabled: Boolean(visitId),
  });

  if (patient.data && (!visitId || reopened.data)) {
    const opened = visitId && visitId !== created ? visitId : "";
    return <Visit key={`${patient.data.patient_id}:${opened}`} patient={patient.data} reopened={opened ? reopened.data : undefined} onCreated={setCreated} />;
  }
  return (
    <Frame patientId={patientId} state="not_checked">
      <PaneContent>
        {(patient.isPending || reopened.isLoading) && <p className="text-muted-foreground">Loading the record…</p>}
        {patient.isError && <p role="alert">{errorText(patient.error)}</p>}
        {reopened.isError && <p role="alert">{errorText(reopened.error)}</p>}
      </PaneContent>
    </Frame>
  );
}

// What one check sends: the note as written and whether the AI review runs ("Run the AI review
// again" sends it on whatever the box says).
type CheckRequest = { note: string; useAi: boolean };
type CheckMutation = UseMutationResult<VisitCheck, Error, CheckRequest>;

function Visit({ patient, reopened, onCreated }: { patient: PatientDetail; reopened?: SavedVisit; onCreated: (visitId: string) => void }) {
  const [note, setNote] = useState(reopened?.note ?? String(patient.today_encounter.note ?? ""));
  const [useAi, setUseAi] = useState(false);
  const router = useRouter();
  const queryClient = useQueryClient();
  const check: CheckMutation = useMutation({
    mutationFn: async (req: CheckRequest) =>
      unwrap(
        await api.POST("/api/patients/{patient_id}/visits", {
          params: { path: { patient_id: patient.patient_id } },
          body: { note: req.note, use_ai: req.useAi },
        }),
      ),
    onSuccess: (done, req) => {
      // The saved visit as GET /api/visits/{id} would send it, so reopening it needs no fetch.
      const asSaved: SavedVisit = {
        ...done,
        note: req.note,
        decisions: [],
        all_resolved: done.cards.length === 0,
        unresolved: done.cards.map((c) => c.extension.alert_id),
        finalized_at: null,
        plan: null, // plans are made only from Compare plans
      };
      queryClient.setQueryData(["visit", done.visit_id], asSaved);
      refreshDay(queryClient, patient.patient_id);
      // The address names the saved visit, so Back or a reload reopens it, never a blank form.
      onCreated(done.visit_id);
      router.replace(visitHref(patient.patient_id, done.visit_id));
    },
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

  // The visit on screen: a new check's result, else the saved visit reopened (until a new check runs).
  const result: VisitCheck | undefined = check.data ?? (check.isIdle ? reopened : undefined);
  // The AI review this run: the box, unless "Run the AI review again" asked for it.
  const aiThisRun = check.variables?.useAi ?? useAi;
  return (
    <VisitView
      key={result?.visit_id ?? "before"}
      result={result}
      reopened={result === reopened ? reopened : undefined}
      patient={patient}
      check={check}
      notesForm={notesForm}
      aiThisRun={aiThisRun}
      retryAi={() => check.mutate({ note, useAi: true })}
    />
  );
}

/** Which screen the pane shows. The results screen comes first after the checks (owner, 2026-11-26). */
type View =
  | { name: "notes" }
  | { name: "results" }
  | { name: "alert"; i: number }
  | { name: "override"; i: number; other: boolean }
  | { name: "plan" }
  | { name: "finalize"; confirming: boolean };

function VisitView({
  patient,
  check,
  result,
  reopened,
  notesForm,
  aiThisRun,
  retryAi,
}: {
  patient: PatientDetail;
  check: CheckMutation;
  /** The visit on screen: a new check's result, or the saved visit reopened. */
  result: VisitCheck | undefined;
  /** Set when the visit on screen is a saved one reopened: its decisions so far. */
  reopened: SavedVisit | undefined;
  notesForm: React.ReactNode;
  aiThisRun: boolean;
  retryAi: () => void;
}) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const day = useClinicDay().data;
  const visitId = result?.visit_id;
  const [view, setView] = useState<View>(result ? { name: "results" } : { name: "notes" });
  const [saved, setSaved] = useState<DecisionOut[]>(reopened?.decisions ?? []);
  const [finalizeNote, setFinalizeNote] = useState<string | null>(reopened ? reopened.finalize_note : (result?.finalize_note ?? null));
  const [finalizedAt, setFinalizedAt] = useState<string | null>(reopened?.finalized_at ?? null);
  const [comment, setComment] = useState("");
  // The AI's management plan, made only from "Compare plans" (owner, 2026-11-27); a reopened visit
  // brings its latest one.
  const [plan, setPlan] = useState<ManagementPlan | null>(reopened?.plan ?? null);
  const compare = useMutation({
    mutationFn: async () =>
      unwrap(await api.POST("/api/visits/{visit_id}/plan", { params: { path: { visit_id: result!.visit_id } } })),
    onMutate: () => setView({ name: "plan" }),
    onSuccess: (made) => {
      setPlan(made);
      keepSaved(queryClient, visitId, { plan: made });
    },
  });
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
      keepSaved(queryClient, visitId, { decisions: reply.decisions, finalize_note: reply.finalize_note, all_resolved: reply.all_resolved, unresolved: reply.unresolved });
      refreshDay(queryClient, patient.patient_id);
      // On to the next alert still to review, or back to the results when none is left.
      const ids = result!.cards.map((c) => c.extension.alert_id);
      const decided = new Set(reply.decisions.map((d) => d.alert_id));
      const next = nextToReview(ids, decided, ids.indexOf(decision.alert_id));
      setView(next === null ? { name: "results" } : { name: "alert", i: next });
    },
  });
  const finalize = useMutation({
    mutationFn: async () =>
      unwrap(await api.POST("/api/visits/{visit_id}/finalize", { params: { path: { visit_id: result!.visit_id } } })),
    onSuccess: (reply) => {
      setSaved(reply.decisions);
      setFinalizedAt(reply.finalized_at);
      keepSaved(queryClient, visitId, { decisions: reply.decisions, finalized_at: reply.finalized_at });
      refreshDay(queryClient, patient.patient_id);
    },
  });
  const savedByAlert = new Map(saved.map((d) => [d.alert_id, d]));
  const state: VisitState = check.isPending ? "checking" : (result?.status ?? "not_checked");
  const card = (view.name === "alert" || view.name === "override") && result ? result.cards[view.i] : undefined;
  const next = day ? nextPatient(day.appointments, patient.patient_id) : null;

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
            saving: save.isPending || finalize.isPending,
            plan: planState(plan, compare.status),
            comparePlans: () => {
              if (!compare.isPending) compare.mutate();
            },
            patientName: patient.name,
            comment,
            finalizedAt,
            next,
            go: (v) => {
              setComment("");
              setView(v);
            },
            accept: () => card && decide(acceptDecision(card.extension.alert_id)),
            saveOther: () => card && decide(overrideDecision(card.extension.alert_id, NEEDS_COMMENT, comment)),
            retryAi,
            askToFinalize: () => setView({ name: "finalize", confirming: true }),
            cancelFinalize: () => setView({ name: "finalize", confirming: false }),
            finalize: () => {
              if (!finalize.isPending) finalize.mutate();
            },
            open: (href) => router.push(href),
          })}
        />
      }
    >
      <PaneHeader title={patient.name} meta={patientLine(patient)} aside={<StatusChip state={state} finalized={Boolean(finalizedAt)} />} />
      <PaneContent>
        {result && finalizedAt && view.name !== "plan" ? (
          <RecordView check={result} savedByAlert={savedByAlert} finalizedAt={finalizedAt} />
        ) : (
          <>
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
                noteSent={check.variables?.note ?? reopened?.note ?? ""}
                savedByAlert={savedByAlert}
                finalizeNote={finalizeNote}
                saveError={save.isError ? errorText(save.error) : null}
                onOpen={(i) => setView({ name: "alert", i })}
              />
            )}
            {card && view.name === "alert" && (
              <AlertView card={card} n={view.i + 1} patientName={patient.name} visitDate={result?.visit_date ?? ""} />
            )}
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
            {result && view.name === "plan" && (
              <PlanView plan={plan} pending={compare.isPending} error={compare.isError ? errorText(compare.error) : null} />
            )}
            {result && view.name === "finalize" && (
              <FinalizeView
                check={result}
                patientName={patient.name}
                savedByAlert={savedByAlert}
                finalizeNote={finalizeNote}
                onReview={(i) => setView({ name: "alert", i })}
              />
            )}
            {(save.isError || finalize.isError) && view.name !== "results" && (
              <p role="alert" className="mt-4 text-red">
                {errorText(finalize.isError ? finalize.error : save.error)}
              </p>
            )}
          </>
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
 * The tray for where the visit is. The prompts are the design's (S2, S3, S4, S4d, S6a, S6b, S7a);
 * the results-screen prompts are new with that screen (owner, 2026-11-26), and the confirm before
 * finalizing is the owner's decision 6.
 */
function trayFor(t: {
  view: View;
  pending: boolean;
  runningStatus: React.ReactNode;
  result: VisitCheck | undefined;
  savedByAlert: Map<string, DecisionOut>;
  saving: boolean;
  plan: PlanState;
  comparePlans: () => void;
  patientName: string;
  comment: string;
  finalizedAt: string | null;
  next: DayAppointment | null;
  go: (v: View) => void;
  accept: () => void;
  saveOther: () => void;
  retryAi: () => void;
  askToFinalize: () => void;
  cancelFinalize: () => void;
  finalize: () => void;
  open: (href: string) => void;
}): TrayProps {
  const { view, result, savedByAlert, saving, go } = t;
  const later = { plan: "todo", finalize: "todo" } as const;
  if (t.pending) {
    return { notes: "done", checks: "current", alerts: [], ...later, lead: "Checks running.", rest: "Results open by themselves.", status: t.runningStatus };
  }
  const runChecks: TrayButton = { label: "Run checks", form: NOTES_FORM };
  if (!result) {
    return { notes: "current", checks: "todo", alerts: [], ...later, lead: "Clinical notes.", rest: "Write your plan, then run checks.", primary: runChecks };
  }

  const ids = result.cards.map((c) => c.extension.alert_id);
  const decided = new Set(savedByAlert.keys());
  const first = firstName(t.patientName);

  // Finalized: the record, read only, and on to the next patient (S6b).
  if (t.finalizedAt) {
    const next = t.next;
    return {
      notes: "done",
      checks: "done",
      alerts: ids.map((): Step => "done"),
      plan: view.name === "plan" ? "current" : t.plan === "good" ? "done" : "todo",
      finalize: "done",
      // A finalized visit keeps its plan to read; the Finalize step goes back to the record.
      go: { plan: t.plan === "none" ? undefined : () => go({ name: "plan" }), finalize: () => go({ name: "results" }) },
      lead: "Saved.",
      rest: next ? `Next: ${next.name}, ${next.time}.` : "Every visit today is finalized.",
      primary: next
        ? { label: `Next patient: ${firstName(next.name)}`, onClick: () => t.open(visitHref(next.patient_id, next.visit_id)) }
        : { label: "Back to day", onClick: () => t.open("/") },
    };
  }

  const current = view.name === "alert" || view.name === "override" ? view.i : null;
  const steps = {
    notes: (view.name === "notes" ? "current" : "done") as Step,
    checks: (view.name === "results" ? "current" : "done") as Step,
    alerts: ids.map((id, i): Step => (i === current ? "current" : decided.has(id) ? "done" : "todo")),
    plan: (view.name === "plan" ? "current" : t.plan === "good" ? "done" : "todo") as Step,
    finalize: (view.name === "finalize" ? "current" : "todo") as Step,
    go: {
      notes: () => go({ name: "notes" }),
      checks: () => go({ name: "results" }),
      alert: (i: number) => go({ name: "alert", i }),
      plan: t.plan === "none" ? undefined : () => go({ name: "plan" }),
      finalize: () => go({ name: "finalize", confirming: false }),
    },
  };
  // A good plan is kept: pressing again shows it with no new AI call. A failed or flagged one, or a
  // refusal, can be tried again (owner, 2026-11-27). A check that wasn't saved has no visit to plan.
  const compareButton: TrayButton = {
    label: "Compare plans",
    onClick: t.plan === "good" ? () => go({ name: "plan" }) : t.comparePlans,
    disabled: !result.record_saved,
  };
  const toFinalize: TrayButton = { label: "Go to finalize", onClick: () => go({ name: "finalize", confirming: false }) };
  const retry: TrayButton = { label: "Run the AI review again", onClick: t.retryAi };
  const of = (i: number) => `Alert ${i + 1} of ${ids.length}.`;
  const left = ids.filter((id) => !decided.has(id)).length;
  const finalizeButton: TrayButton = left
    ? { label: "Finalize visit", locked: true }
    : { label: "Finalize visit", onClick: t.askToFinalize, disabled: saving || !result.record_saved };

  if (view.name === "finalize") {
    if (view.confirming && !left) {
      return {
        ...steps,
        lead: `Finalize ${first}'s visit?`,
        rest: "Decisions can't be changed after this.",
        primary: { label: "Finalize", onClick: t.finalize, disabled: saving },
        secondary: { label: "Go back", onClick: t.cancelFinalize },
      };
    }
    return left
      ? { ...steps, lead: "Finalize is locked.", rest: `${left} ${left === 1 ? "alert" : "alerts"} left to review.`, primary: finalizeButton }
      : { ...steps, lead: "Finalize.", rest: "Every alert has your answer.", primary: finalizeButton };
  }
  if (view.name === "plan") {
    if (t.plan === "comparing") return { ...steps, lead: "Comparing plans." };
    return t.plan === "good"
      ? { ...steps, lead: "Plan.", rest: "To change it, go back to Clinical notes.", primary: toFinalize }
      : { ...steps, lead: "Plan.", rest: "Try again, or go to finalize.", primary: toFinalize, secondary: compareButton };
  }
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
        : `Does it apply to ${first} today?`,
      primary: { label: "Accept alert", onClick: t.accept, disabled: saving || !result.record_saved },
      secondary: { label: "Override", onClick: () => go({ name: "override", i: view.i, other: false }), disabled: saving || !result.record_saved },
    };
  }
  if (view.name === "override") {
    return {
      ...steps,
      lead: of(view.i),
      rest: view.other ? "Say why, then save the override." : "Tap a reason to save the override.",
      primary: view.other ? { label: "Save override", onClick: t.saveOther, disabled: saving || !t.comment.trim() } : undefined,
      secondary: { label: "Back to the alert", onClick: () => go({ name: "alert", i: view.i }) },
    };
  }

  // The results screen. With every alert answered (or none raised), the next step is Finalize.
  const firstOpen = ids.findIndex((id) => !decided.has(id));
  const review: TrayButton | undefined = firstOpen >= 0 ? { label: `Review alert ${firstOpen + 1}`, onClick: () => go({ name: "alert", i: firstOpen }) } : undefined;
  // Every alert answered: next is Compare plans (S5), except with no guideline search, when no
  // plan can be made.
  const main = review ?? (result.ai_review === "search_unavailable" ? finalizeButton : compareButton);
  switch (result.ai_review) {
    case "failed":
    case "unreadable":
      return { ...steps, lead: "AI review failed.", rest: "Try again, or use rule checks only.", primary: main, secondary: retry };
    case "cut_off":
    case "partly_read":
      return {
        ...steps,
        lead: "AI review incomplete.",
        rest: ids.length ? "Review the alerts it read." : "Try again, or use rule checks only.",
        primary: main,
        secondary: retry,
      };
    case "search_unavailable":
      return { ...steps, lead: "Guideline search unavailable.", rest: "Rule checks only.", primary: main };
    default:
      if (!ids.length) return { ...steps, lead: "Checks done.", rest: "No alerts to review.", primary: main };
      return review
        ? { ...steps, lead: `${ids.length} ${ids.length === 1 ? "alert" : "alerts"} to review.`, rest: "Accept or override each one.", primary: review }
        : { ...steps, lead: "Every alert has your answer.", rest: savedSummary(savedByAlert), primary: main };
  }
}

function savedSummary(saved: Map<string, DecisionOut>): string {
  const words = [...saved.values()].map(decisionWords);
  const accepted = words.filter((w) => w === "Accepted").length;
  const overridden = words.length - accepted;
  return [accepted && `${accepted} accepted`, overridden && `${overridden} overridden`].filter(Boolean).join(", ") + ".";
}

/** After a check, a decision or a finalize: the day, its rail and the past checks show it. */
function refreshDay(queryClient: QueryClient, patientId: string) {
  void queryClient.invalidateQueries({ queryKey: ["clinic-day"] });
  void queryClient.invalidateQueries({ queryKey: ["past-checks", patientId] });
}

/** Keep the cached saved visit in step, so reopening it (board, rail, past checks) is never stale. */
function keepSaved(queryClient: QueryClient, visitId: string | undefined, change: Partial<SavedVisit>) {
  if (!visitId) return;
  queryClient.setQueryData<SavedVisit>(["visit", visitId], (old) => (old ? { ...old, ...change } : old));
}
