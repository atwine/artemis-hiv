"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { use, useId, useState } from "react";

import { api, errorText, unwrap, type Card, type DecisionOut, type Decisions, type PatientDetail, type VisitCheck } from "@/lib/api/client";
import { decisionsToSave, type Draft, type Reason } from "@/lib/decisions";

export function VisitScreen({ params }: { params: Promise<{ patientId: string }> }) {
  const { patientId } = use(params);
  const patient = useQuery({
    queryKey: ["patient", patientId],
    queryFn: async () =>
      unwrap(await api.GET("/api/patients/{patient_id}", { params: { path: { patient_id: patientId } } })),
  });

  return (
    <main>
      <p>
        <Link href="/">Back to patients</Link>
      </p>
      {patient.isPending && <p>Loading the record…</p>}
      {patient.isError && <p role="alert">{errorText(patient.error)}</p>}
      {patient.data && <Visit key={patient.data.patient_id} patient={patient.data} />}
    </main>
  );
}

function Visit({ patient }: { patient: PatientDetail }) {
  const [note, setNote] = useState(String(patient.today_encounter.note ?? ""));
  const [useAi, setUseAi] = useState(false);
  const check = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/patients/{patient_id}/visits", {
          params: { path: { patient_id: patient.patient_id } },
          body: { note, use_ai: useAi, include_plan: false },
        }),
      ),
  });

  return (
    <>
      <h1>{patient.name}</h1>
      <p>
        {patient.patient_id} · {patient.age_years ?? "?"} {patient.sex} · ART {patient.art_regimen_current.join("/")} ·
        visit {String(patient.today_encounter.date)}
      </p>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          check.mutate();
        }}
      >
        <label>
          Clinical notes
          <br />
          <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={6} cols={80} maxLength={20000} />
        </label>
        <br />
        <label>
          <input type="checkbox" checked={useAi} onChange={(e) => setUseAi(e.target.checked)} /> AI review
        </label>
        <br />
        <button type="submit" disabled={check.isPending}>
          Run checks
        </button>
        {check.isPending && <span> Running the checks…</span>}
      </form>

      {check.isError && <p role="alert">{errorText(check.error)}</p>}
      {check.data && <Results key={check.data.visit_id} check={check.data} />}
    </>
  );
}

function Results({ check }: { check: VisitCheck }) {
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [saved, setSaved] = useState<Decisions | null>(null);
  const toSave = decisionsToSave(drafts);
  const save = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/visits/{visit_id}/decisions", {
          params: { path: { visit_id: check.visit_id } },
          body: { decisions: toSave ?? [] },
        }),
      ),
    onSuccess: (reply) => {
      setSaved(reply);
      setDrafts({});
    },
  });
  const savedByAlert = new Map((saved?.decisions ?? []).map((d) => [d.alert_id, d]));
  const finalizeNote = saved ? saved.finalize_note : check.finalize_note;

  return (
    <section aria-label="Check results">
      <h2>Check results</h2>
      {check.banners.map((b, i) => (
        <p key={i} role="status" data-level={b.level}>
          {b.text}
        </p>
      ))}
      {!check.record_saved && <p role="alert">This check could not be saved, so its alerts cannot be decided here.</p>}

      {check.cards.map((card) => (
        <AlertCard
          key={card.uuid}
          card={card}
          draft={drafts[card.extension.alert_id]}
          saved={savedByAlert.get(card.extension.alert_id)}
          onChange={(d) => setDrafts((all) => ({ ...all, [card.extension.alert_id]: d }))}
        />
      ))}

      {check.cards.length > 0 && (
        <p>
          <button type="button" disabled={!toSave || save.isPending || !check.record_saved} onClick={() => save.mutate()}>
            Save decisions
          </button>
          {save.isError && <span role="alert"> {errorText(save.error)}</span>}
        </p>
      )}
      {finalizeNote && <p>{finalizeNote}</p>}
      <footer>
        <p>{check.disclaimer}</p>
      </footer>
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
    <article aria-labelledby={`${id}-heading`}>
      <h3 id={`${id}-heading`}>{ext.heading}</h3>
      <p>{card.detail}</p>
      {card.suggestions.map((s) => (
        <p key={s.uuid}>{s.label}</p>
      ))}
      {ext.explanation && <p>{ext.explanation}</p>}

      <h4>{ext.references_heading}</h4>
      <ul>
        {ext.references.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>

      <fieldset>
        <legend>Decision</legend>
        {(["Acknowledge", "Override"] as const).map((action) => (
          <label key={action}>
            <input
              type="radio"
              name={`${id}-action`}
              value={action}
              checked={draft?.action === action}
              onChange={() => onChange({ ...current, action })}
            />{" "}
            {action}{" "}
          </label>
        ))}
        {draft?.action === "Override" && (
          <>
            <br />
            <label>
              Override reason{" "}
              <select
                value={draft.reason ?? ""}
                onChange={(e) => onChange({ ...draft, reason: (e.target.value || null) as Reason | null })}
              >
                <option value="">Choose a reason</option>
                {(card.overrideReasons ?? []).map((r) => (
                  <option key={r.code} value={r.display}>
                    {r.display}
                  </option>
                ))}
              </select>
            </label>
            <br />
            <label>
              Comment{" "}
              <textarea value={draft.comment} onChange={(e) => onChange({ ...draft, comment: e.target.value })} maxLength={2000} />
            </label>
          </>
        )}
      </fieldset>
      {saved && (
        <p>
          Saved: {saved.action}
          {saved.reason ? ` (${saved.reason})` : ""}
          {saved.comment ? `: ${saved.comment}` : ""}
        </p>
      )}
    </article>
  );
}
