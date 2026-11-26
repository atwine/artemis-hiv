// The results screen that comes first after the checks (owner, 2026-11-26): the API's banners,
// then each alert as one row. A row opens the alert on its own screen.
import { StatusShape } from "@/components/frame/status";
import type { Card, DecisionOut, PatientDetail, VisitCheck } from "@/lib/api/client";
import { checkedCounts, firstSentence } from "@/lib/record";
import { SOURCE_LABEL, severityWord } from "@/lib/alerts";
import { cn } from "@/lib/utils";

export function ResultsView({
  check,
  patient,
  savedByAlert,
  finalizeNote,
  saveError,
  onOpen,
}: {
  check: VisitCheck;
  patient: PatientDetail;
  savedByAlert: Map<string, DecisionOut>;
  finalizeNote: string | null;
  saveError: string | null;
  onOpen: (i: number) => void;
}) {
  if (check.status === "GREEN" && check.cards.length === 0) return <GreenView check={check} patient={patient} />;
  return (
    <section aria-label="Check results" className="flex max-w-240 flex-col gap-6">
      <h2 className="text-20 font-semibold tracking-[-0.015em]">Check results</h2>
      <Banners check={check} />
      {!check.record_saved && <p role="alert">This check could not be saved, so its alerts cannot be decided here.</p>}
      {/* The list sits on the result row's bottom line, so the two lines don't double up. */}
      {check.cards.length > 0 && (
        <ul aria-label="Alerts" className="-mt-6">
          {check.cards.map((card, i) => (
            <li key={card.uuid} className="border-b border-line">
              <AlertRow card={card} n={i + 1} saved={savedByAlert.get(card.extension.alert_id)} onOpen={() => onOpen(i)} />
            </li>
          ))}
        </ul>
      )}
      {saveError && <p role="alert">{saveError}</p>}
      {finalizeNote && <p className="text-14 text-ink-2">{finalizeNote}</p>}
    </section>
  );
}

/** The decision as the clinician will read it: "Accepted", or "Overridden: <reason>". */
export function decisionWords(d: DecisionOut): string {
  return d.action === "Acknowledge" ? "Accepted" : `Overridden: ${d.reason}`;
}

function AlertRow({ card, n, saved, onOpen }: { card: Card; n: number; saved?: DecisionOut; onOpen: () => void }) {
  const ext = card.extension;
  const severe = ["high", "critical"].includes((ext.severity ?? "").toLowerCase());
  return (
    <button type="button" onClick={onOpen} className="flex min-h-15 w-full cursor-pointer items-center gap-4 py-2 text-left hover:bg-surface">
      <span className="w-5 shrink-0 text-13 text-muted-foreground">{n}</span>
      {ext.severity && <StatusShape state={severe ? "RED" : "AMBER"} size={14} />}
      <span className="flex-1 text-16 text-black">
        {card.summary}
        <span className="ml-2 text-13 text-muted-foreground">
          {[severityWord(ext.severity), SOURCE_LABEL[ext.kind]].filter(Boolean).join(" · ")}
        </span>
      </span>
      <span className={cn("shrink-0 text-15", saved ? "text-green" : "text-ink-2")}>{saved ? decisionWords(saved) : "To review"}</span>
    </button>
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
            "flex items-center gap-4.5 rounded-[14px] border-2 px-6 py-5.5",
            boxed.level === "error" ? "border-red bg-red-wash" : "border-amber bg-amber-wash",
          )}
        >
          <StatusShape state={boxed.level === "error" ? "RED" : "AMBER"} size={30} />
          <p className="text-16 font-medium text-ink">{boxed.text}</p>
        </div>
      )}
      {rows.map((b, i) => (
        <p key={i} role="status" data-level={b.level} className="flex h-15 items-center border-y border-line text-16 text-black">
          {b.text}
        </p>
      ))}
    </>
  );
}

/**
 * A visit with no alerts (Paper FINAL S7b): the API's banner as the headline (its first sentence
 * bold, as the design sets it; no words change), then what was checked, from the record, so a
 * quiet screen never looks like a skipped one. The design's guideline-passage count is left off:
 * the API doesn't say how many passages the AI was shown.
 */
function GreenView({ check, patient }: { check: VisitCheck; patient: PatientDetail }) {
  const banner = check.banners[0];
  const [lead, rest] = firstSentence(banner?.text ?? "");
  return (
    <section aria-label="Check results" className="flex flex-col gap-6">
      <div role="status" data-level={banner?.level} className="flex items-center gap-4.5">
        {banner?.level === "success" && (
          <svg width="44" height="44" viewBox="0 0 14 14" aria-hidden className="shrink-0">
            <circle cx="7" cy="7" r="7" fill="var(--color-green)" />
            <path d="M4 7.2l2 2 4-4.4" fill="none" stroke="#fff" strokeWidth="1.4" />
          </svg>
        )}
        <h2 className="text-30 font-semibold tracking-[-0.025em] text-black">
          {lead} {rest && <span className="text-muted-foreground">{rest}</span>}
        </h2>
      </div>
      {check.banners.slice(1).map((b, i) => (
        <p key={i} role="status" data-level={b.level} className="text-16 text-black">
          {b.text}
        </p>
      ))}
      <div className="flex flex-col gap-3.5">
        <p className="text-13 font-semibold tracking-[0.06em] text-muted-foreground uppercase">
          What was checked, so a quiet screen is not a skipped one
        </p>
        <ul aria-label="What was checked" className="flex overflow-clip rounded-[14px] border border-line">
          {checkedCounts(patient).map((c) => (
            <li key={c.label} className="flex flex-1 flex-col gap-1 border-r border-line px-5.5 py-5 last:border-r-0">
              <span className="text-36 font-semibold tracking-[-0.02em] text-black">{c.n}</span>
              <span className="text-15 text-ink-2">{c.label}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
