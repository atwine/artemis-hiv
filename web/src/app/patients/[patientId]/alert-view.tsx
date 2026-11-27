// One alert on its own screen (Paper FINAL S4b/S4c), with the owner's choices of 2026-11-26:
// a severity tag and a source tag, then the title with the finding in grey; the patient's values
// the alert is about, as recorded, beside the guideline line (the backend's key sentence, or a
// passage's first lines when it sends none), with a button for the whole passage. Accept and
// Override live in the tray.
import { useId, useState } from "react";

import { StatusShape } from "@/components/frame/status";
import type { Card } from "@/lib/api/client";
import { guidelineQuote, isSevere, severityWord, SOURCE_LABEL, valueHeading } from "@/lib/alerts";
import { asSentence } from "@/lib/record";
import { cn } from "@/lib/utils";

export function AlertView({ card, n, patientName, visitDate }: { card: Card; n: number; patientName: string; visitDate: string }) {
  const ext = card.extension;
  const quote = guidelineQuote(ext);
  const suggestion = card.suggestions[0]?.label;
  const values = ext.values ?? [];
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
      <div className="flex min-h-0 overflow-clip rounded-[14px] border border-line">
        {values.length > 0 && (
          <ul aria-label="Patient values" className="flex w-82.5 shrink-0 flex-col gap-4 bg-surface px-6 py-5.5">
            {values.map((v) => (
              <li key={`${v.label}-${v.date}`} className="flex flex-col gap-1.5">
                <span className="text-13 font-semibold tracking-[0.06em] text-muted-foreground uppercase">
                  {valueHeading(patientName, v.date, visitDate)}
                </span>
                <span className="flex items-baseline gap-2.5">
                  <span className="text-52 font-semibold tracking-[-0.03em] text-black">{v.value}</span>
                  <span className="text-15 text-ink-2">{v.unit ? `${v.label}, ${v.unit}` : v.label}</span>
                </span>
              </li>
            ))}
          </ul>
        )}
        {quote ? (
          <Guideline
            heading={ext.references_heading}
            quote={quote.text}
            whole={quote.whole}
            isKeySentence={quote.isKeySentence}
            citation={quote.citation}
            others={ext.references.filter((r) => r !== quote.citation)}
            divided={values.length > 0}
          />
        ) : ext.references.length === 0 ? (
          // Nothing to list (an AI alert that cited no passage): the API's heading says so, as one
          // plain line, not a column label over an empty box.
          <p className={cn("flex flex-1 items-center px-6.5 py-5.5 text-16 font-medium text-ink-2", values.length > 0 && "border-l border-line")}>
            {ext.references_heading}
          </p>
        ) : (
          <div className={cn("flex flex-1 flex-col gap-2.5 rounded-btn border-[1.5px] border-dashed border-line-strong px-6.5 py-5.5", values.length > 0 ? "m-3.5" : "m-0 border-0")}>
            <p className="text-13 font-semibold tracking-[0.06em] text-muted-foreground uppercase">{ext.references_heading}</p>
            {ext.references.map((line) => (
              <p key={line} className="text-19 leading-7 font-medium text-black">
                {line}
              </p>
            ))}
          </div>
        )}
      </div>
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

/**
 * The guideline column of S4c: its heading, the line quoted (the key sentence in full, or the
 * passage's first lines), the citation, and the whole passage one click away.
 */
function Guideline({
  heading,
  quote,
  whole,
  isKeySentence,
  citation,
  others,
  divided,
}: {
  heading: string;
  quote: string;
  whole: string;
  isKeySentence: boolean;
  citation: string;
  others: string[];
  divided: boolean;
}) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <div className={cn("flex min-w-0 flex-1 flex-col gap-2.5 px-6.5 py-5.5", divided && "border-l border-line")}>
      <p className="text-13 font-semibold tracking-[0.06em] text-muted-foreground uppercase">{heading}</p>
      <p id={isKeySentence ? undefined : id} className={cn("max-w-[78ch] font-serif text-19 text-black", !isKeySentence && !open && "line-clamp-3")}>
        “{(isKeySentence ? quote : whole).trim()}”
      </p>
      {isKeySentence && open && (
        <p id={id} className="max-w-[78ch] font-serif text-16 leading-6 text-ink-2">
          {whole.trim()}
        </p>
      )}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <span className="text-14 text-ink-2">{citation}</span>
        <button type="button" aria-expanded={open} aria-controls={id} onClick={() => setOpen(!open)} className="cursor-pointer text-14 font-medium text-blue">
          {open ? "Show less" : "Show the whole passage"}
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
