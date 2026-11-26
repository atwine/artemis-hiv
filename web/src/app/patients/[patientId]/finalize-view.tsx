// Finalize (Paper FINAL S6a) and the saved visit record (S6b). Finalize unlocks when every alert
// has an answer; the confirm step lives in the tray (owner's decision 6). A finalized visit shows
// only its record: reopening it never asks the AI again and offers nothing to change.
import { StatusShape } from "@/components/frame/status";
import type { DecisionOut, VisitCheck } from "@/lib/api/client";
import { clock } from "@/lib/day";
import { firstName } from "@/lib/alerts";
import { aiReviewWords, decisionLine, stillToReview } from "@/lib/visit";
import { cn } from "@/lib/utils";

function Done() {
  return (
    <svg width="20" height="20" viewBox="0 0 14 14" aria-hidden className="shrink-0">
      <circle cx="7" cy="7" r="7" fill="var(--color-ink)" />
      <path d="M4 7.2l2 2 4-4.4" fill="none" stroke="#fff" strokeWidth="1.6" />
    </svg>
  );
}

export function FinalizeView({
  check,
  patientName,
  savedByAlert,
  finalizeNote,
  onReview,
}: {
  check: VisitCheck;
  patientName: string;
  savedByAlert: Map<string, DecisionOut>;
  finalizeNote: string | null;
  onReview: (i: number) => void;
}) {
  const ids = check.cards.map((c) => c.extension.alert_id);
  const decided = new Set(savedByAlert.keys());
  const left = stillToReview(ids, decided);
  const firstOpen = ids.findIndex((id) => !decided.has(id));
  const ran = clock(check.saved_at);
  return (
    <section aria-label="Finalize" className="flex flex-col gap-6">
      <h2 className="max-w-250 text-30 font-semibold tracking-[-0.025em] text-black">
        Finalize {firstName(patientName)}&apos;s visit.{" "}
        <span className="text-muted-foreground">
          {left ? "It unlocks when every alert has your answer." : "Every alert has your answer."}
        </span>
      </h2>
      <ul className="flex max-w-215 flex-col border-t border-line">
        <li className="flex h-14.5 items-center gap-4 border-b border-line">
          <Done />
          <span className="flex-1 text-16 text-black">Clinical notes</span>
          <span className="text-14 text-ink-2">Saved {ran}</span>
        </li>
        <li className="flex h-14.5 items-center gap-4 border-b border-line">
          <Done />
          <span className="flex-1 text-16 text-black">{check.ai_review === "not_run" ? "Checks: rules only" : "Checks: rules and AI review"}</span>
          <span className="text-14 text-ink-2">Ran {ran}</span>
        </li>
        {ids.length > 0 && (
          <li className={cn("flex min-h-18 items-center gap-4 border-b border-line", left && "-mx-3.5 bg-red-wash px-3.5")}>
            {left ? <StatusShape state="RED" size={20} /> : <Done />}
            <span className="flex flex-1 flex-col gap-0.5 py-2">
              <span className={cn("text-16 text-black", left && "font-semibold")}>
                Alerts: {decided.size} of {ids.length} reviewed
              </span>
              {left && <span className="text-14 text-ink-2">{left}</span>}
            </span>
            {left && (
              <button type="button" onClick={() => onReview(firstOpen)} className="cursor-pointer text-15 font-semibold text-blue">
                Review alert {firstOpen + 1} <span aria-hidden>→</span>
              </button>
            )}
          </li>
        )}
      </ul>
      {finalizeNote && <p className="max-w-215 text-14 text-ink-2">{finalizeNote}</p>}
      <p className="max-w-215 text-15 leading-[18px] text-ink-2">
        Finalizing saves the visit record: what was checked, what the screen showed, and what you decided and why.
      </p>
    </section>
  );
}

export function RecordView({
  check,
  savedByAlert,
  finalizedAt,
}: {
  check: VisitCheck;
  savedByAlert: Map<string, DecisionOut>;
  finalizedAt: string;
}) {
  const facts: [string, string][] = [
    ["Visit", check.visit_id],
    ["Checks run", `${clock(check.saved_at)} · finalized ${clock(finalizedAt)}`],
    ["Model", check.model ?? "None: rule checks only"],
    ["AI review", aiReviewWords(check.ai_review)],
  ];
  return (
    <section aria-label="Visit record" className="flex flex-col gap-6">
      <h2 className="text-30 font-semibold tracking-[-0.025em] text-black">
        Visit finalized {clock(finalizedAt)}.{" "}
        <span className="text-muted-foreground">Reopening it shows this record; the AI is not asked again.</span>
      </h2>
      <div className="flex gap-10">
        <dl className="flex w-105 shrink-0 flex-col border-t border-line">
          {facts.map(([label, text]) => (
            <div key={label} className="flex border-b border-line py-[9px] text-14 leading-5">
              <dt className="w-32.5 shrink-0 text-muted-foreground">{label}</dt>
              <dd className="min-w-0 break-all text-black">{text}</dd>
            </div>
          ))}
        </dl>
        <ol aria-label="Decisions" className="flex min-w-0 flex-1 flex-col border-t border-line">
          {check.cards.length === 0 && <li className="border-b border-line py-[9px] text-14 leading-5 text-ink-2">No alerts to decide.</li>}
          {check.cards.map((card, i) => {
            const d = savedByAlert.get(card.extension.alert_id);
            return (
              <li key={card.uuid} className="flex gap-4 border-b border-line py-[9px] text-14 leading-5">
                <span className="flex flex-1 flex-col gap-0.5">
                  <span className="text-black">
                    {i + 1} · {card.summary}
                  </span>
                  {d?.comment && <span className="text-muted-foreground">“{d.comment}”</span>}
                </span>
                <span className="w-62.5 shrink-0 text-ink-2">{d ? decisionLine(d) : "No decision"}</span>
              </li>
            );
          })}
        </ol>
      </div>
    </section>
  );
}
