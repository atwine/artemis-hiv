// Overriding an alert (Paper FINAL S4d): one tap on a reason saves it. "Other (say why)" opens a
// comment box instead, saved from the tray. The reasons are the card's own list from the API.
// The design's strip of the patient's value against the guideline line waits for the backend's
// per-alert values (owner, 2026-11-26), like the alert screen's value box.
import type { Card } from "@/lib/api/client";
import type { Reason } from "@/lib/decisions";
import { NEEDS_COMMENT } from "@/lib/decisions";
import { cn } from "@/lib/utils";

export function OverrideView({
  card,
  n,
  other,
  comment,
  busy,
  onReason,
  onComment,
}: {
  card: Card;
  n: number;
  other: boolean;
  comment: string;
  busy: boolean;
  onReason: (reason: Reason) => void;
  onComment: (text: string) => void;
}) {
  return (
    <section aria-label={`Override alert ${n}`} className="flex flex-col gap-6">
      <div className="flex flex-col gap-3">
        <p className="text-14 text-ink-2">
          Overriding alert {n} · {card.summary}
        </p>
        <h2 className="text-30 font-semibold tracking-[-0.025em] text-black">
          Why does it not apply? <span className="text-muted-foreground">One tap saves your reason.</span>
        </h2>
      </div>
      <ul aria-label="Override reasons" className="flex max-w-[852px] flex-wrap gap-3">
        {(card.overrideReasons ?? []).map((r) => {
          const needsComment = r.display === NEEDS_COMMENT;
          const chosen = needsComment && other;
          return (
            <li key={r.code}>
              <button
                type="button"
                disabled={busy}
                aria-pressed={needsComment ? chosen : undefined}
                // The reasons are the API's own list for this card; the backend checks the one sent.
                onClick={() => onReason(r.display as Reason)}
                className={cn(
                  "flex h-14.5 w-105 cursor-pointer items-center justify-between rounded-[12px] border border-line-strong px-5 text-left text-16 font-medium text-black hover:bg-surface disabled:cursor-wait",
                  needsComment && "border-dashed",
                  chosen && "border-solid border-button bg-surface",
                )}
              >
                {r.display}
                {needsComment && !chosen && <span className="text-14 font-normal text-muted-foreground">opens a comment box</span>}
              </button>
            </li>
          );
        })}
      </ul>
      {other && (
        <label className="flex max-w-[852px] flex-col gap-2">
          <span className="text-15 font-semibold text-black">Why does it not apply?</span>
          <textarea
            value={comment}
            onChange={(e) => onComment(e.target.value)}
            maxLength={2000}
            rows={3}
            autoFocus
            className="rounded-btn border border-line-strong p-3 text-15 leading-[22px]"
          />
        </label>
      )}
    </section>
  );
}
