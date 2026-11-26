// The day rail: today's visits down the left edge, each a label and its status shape. Dimmed on
// visit screens so the pane leads; 85%, not the design's 55%, keeps the times at 4.5:1 contrast (owner).
import Link from "next/link";

import { cn } from "@/lib/utils";

import { StatusShape, type VisitState } from "./status";

export type RailEntry = { id: string; label: string; name: string; href: string; state: VisitState };

export function DayRail({ entries, currentId, dimmed }: { entries: RailEntry[]; currentId?: string; dimmed?: boolean }) {
  return (
    <nav aria-label="Today's patients" className={cn("flex w-19 shrink-0 flex-col gap-0.5 pt-2", dimmed && "opacity-85")}>
      {entries.map((e) => {
        const current = e.id === currentId;
        return (
          <Link
            key={e.id}
            href={e.href}
            aria-current={current ? "page" : undefined}
            aria-label={`${e.label}, ${e.name}`}
            className={cn(
              "flex h-13 shrink-0 flex-col items-center justify-center gap-1 text-12",
              current ? "border-l-3 border-button font-bold text-ink" : "text-ink-2",
            )}
          >
            <span className="max-w-full truncate px-1">{e.label}</span>
            <StatusShape state={e.state} size={12} />
          </Link>
        );
      })}
    </nav>
  );
}
