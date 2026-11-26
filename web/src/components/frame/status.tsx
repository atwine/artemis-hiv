// A visit's state as a shape and a word, so colour never works alone (docs/design/brief.md):
// red = square "!", amber = triangle, green = circle tick, incomplete = dashed circle.
import type { VisitCheck } from "@/lib/api/client";
import { cn } from "@/lib/utils";

/** Before a check has run, while it runs, or the API's overall status once it has. */
export type VisitState = "not_checked" | "checking" | VisitCheck["status"];

export function StatusShape({ state, size }: { state: VisitState; size: 12 | 14 | 30 }) {
  const common = { width: size, height: size, viewBox: "0 0 14 14", "aria-hidden": true, className: "shrink-0" } as const;
  switch (state) {
    case "RED":
      return (
        <svg {...common}>
          <rect width="14" height="14" rx="3" fill="var(--color-red)" />
          <rect x="6" y="3" width="2" height="5" fill="#fff" />
          <rect x="6" y="9.5" width="2" height="2" fill="#fff" />
        </svg>
      );
    case "AMBER":
      return (
        <svg {...common}>
          <path d="M7 1L13.5 12.5H0.5Z" fill="var(--color-amber)" />
        </svg>
      );
    case "GREEN":
      return (
        <svg {...common}>
          <circle cx="7" cy="7" r="7" fill="var(--color-green)" />
          <path d="M4 7.2l2 2 4-4.4" fill="none" stroke="#fff" strokeWidth="1.8" />
        </svg>
      );
    case "INCOMPLETE":
      return (
        <svg {...common}>
          <circle cx="7" cy="7" r="6" fill="none" stroke="var(--color-grey)" strokeWidth="1.6" strokeDasharray="2.5 2" />
        </svg>
      );
    case "checking":
      return null; // the CHECKING chip is the word alone
    case "not_checked":
      return (
        <span
          aria-hidden
          className={cn(
            "shrink-0 rounded-full border-[1.5px] border-solid",
            size === 14 ? "size-3 border-muted-foreground" : "size-2.5 border-line-strong",
          )}
        />
      );
  }
}

const CHIP: Record<VisitState, { label: string; className: string }> = {
  not_checked: { label: "NOT CHECKED", className: "bg-fill text-ink-2" },
  checking: { label: "CHECKING", className: "bg-blue-wash text-checking" },
  RED: { label: "RED", className: "bg-red-wash text-red" },
  AMBER: { label: "AMBER", className: "bg-amber-wash text-amber" },
  GREEN: { label: "GREEN", className: "bg-mint text-green" },
  INCOMPLETE: { label: "INCOMPLETE", className: "bg-fill text-grey" },
};

export function StatusChip({ state }: { state: VisitState }) {
  const chip = CHIP[state];
  return (
    <span className={cn("flex h-7 items-center gap-[7px] rounded-chip px-2.5", chip.className)}>
      <StatusShape state={state} size={14} />
      <span className="text-13 font-semibold tracking-[0.02em]">{chip.label}</span>
    </span>
  );
}
