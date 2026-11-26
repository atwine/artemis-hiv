// One alert on its own screen (Paper FINAL S4b/S4c), with the owner's choices of 2026-11-26:
// a severity tag and a source tag, then the title with the finding in grey; no patient-value
// box until the backend sends the values; the guideline passage's first lines with a button for
// the whole passage. Accept and Override live in the tray.
import { useId, useState } from "react";

import { StatusShape } from "@/components/frame/status";
import type { Card } from "@/lib/api/client";
import { isSevere, SOURCE_LABEL, quotedPassage, severityWord } from "@/lib/alerts";
import { asSentence } from "@/lib/record";
import { cn } from "@/lib/utils";

export function AlertView({ card, n }: { card: Card; n: number }) {
  const ext = card.extension;
  const passage = quotedPassage(ext);
  const suggestion = card.suggestions[0]?.label;
  return (
    <section aria-label={`Alert ${n}`} className="flex flex-col gap-6">
      <div className="flex flex-col gap-3.5">
        <div className="flex gap-2">
          <SeverityTag severity={ext.severity} />
          <span
            className={cn(
              "flex h-6.5 items-center rounded-chip px-[9px] text-13 font-semibold",
              ext.kind === "ai" ? "bg-blue-wash text-checking" : "bg-fill text-ink-2",
            )}
          >
            {SOURCE_LABEL[ext.kind]}
          </span>
        </div>
        <h2 className="max-w-[980px] text-30 font-semibold tracking-[-0.025em] text-black">
          {asSentence(card.summary)} <span className="text-muted-foreground">{card.detail}</span>
        </h2>
        {suggestion && (
          <p className="flex items-baseline gap-2.5">
            <span className="text-13 font-semibold tracking-[0.06em] text-muted-foreground">SUGGESTED</span>
            <span className="text-16 font-medium text-black">{suggestion}</span>
          </p>
        )}
      </div>
      {passage ? (
        <Passage heading={ext.references_heading} text={passage.text} citation={passage.citation ?? ""} others={ext.references.filter((r) => r !== passage.citation)} />
      ) : (
        <div className="flex flex-col gap-2.5 rounded-btn border-[1.5px] border-dashed border-line-strong px-6.5 py-5.5">
          <p className="text-13 font-semibold tracking-[0.06em] text-muted-foreground uppercase">{ext.references_heading}</p>
          {ext.references.map((line) => (
            <p key={line} className="text-19 leading-7 font-medium text-black">
              {line}
            </p>
          ))}
        </div>
      )}
    </section>
  );
}

function SeverityTag({ severity }: { severity: string | null | undefined }) {
  const word = severityWord(severity);
  if (!word) return null;
  const severe = isSevere(severity);
  return (
    <span
      className={cn(
        "flex h-6.5 items-center gap-1.5 rounded-chip px-[9px] text-13 font-semibold",
        severe ? "bg-red-wash text-red" : "bg-amber-wash text-amber",
      )}
    >
      <StatusShape state={severe ? "RED" : "AMBER"} size={12} />
      {word}
    </span>
  );
}

/** The guideline column of S4c: its heading, the passage (first lines, or all of it), the citation. */
function Passage({ heading, text, citation, others }: { heading: string; text: string; citation: string; others: string[] }) {
  const [whole, setWhole] = useState(false);
  const id = useId();
  return (
    <div className="flex flex-col gap-2.5 rounded-[14px] border border-line px-6.5 py-5.5">
      <p className="text-13 font-semibold tracking-[0.06em] text-muted-foreground uppercase">{heading}</p>
      <p id={id} className={cn("max-w-[78ch] font-serif text-19 text-black", !whole && "line-clamp-3")}>
        “{text.trim()}”
      </p>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <span className="text-14 text-ink-2">{citation}</span>
        <button
          type="button"
          aria-expanded={whole}
          aria-controls={id}
          onClick={() => setWhole(!whole)}
          className="cursor-pointer text-14 font-medium text-blue"
        >
          {whole ? "Show less" : "Show the whole passage"}
        </button>
      </div>
      {others.length > 0 && (
        <ul className="text-14 text-ink-2">
          {others.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
