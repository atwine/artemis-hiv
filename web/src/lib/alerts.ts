// Plain functions for the alert screens: what each alert shows and where review goes next.
import type { Card } from "./api/client";
import { longDate } from "./dates.ts";

type Extension = Card["extension"];
type Passage = Extension["passages"][number];

/**
 * The source tag's words, the same as in the API's heading "Alert (Rule check): ..."
 * (artemis/screen_text.py alert_heading). The browser test fails if the two differ.
 */
export const SOURCE_LABEL: Record<Extension["kind"], string> = { ai: "AI review", rule: "Rule check" };

/** High and critical alerts are the red ones (backend/cards.py: both are "critical"). */
export function isSevere(severity: string | null | undefined): boolean {
  return ["high", "critical"].includes((severity ?? "").trim().toLowerCase());
}

/** The API's severity, capitalised ("high" -> "High"); null when it sends none. */
export function severityWord(severity: string | null | undefined): string | null {
  const s = (severity ?? "").trim();
  return s ? s[0].toUpperCase() + s.slice(1).toLowerCase() : null;
}

/**
 * The passage to quote: the first one the alert's references name. None when they name none:
 * the AI cited no passage, or the search was unavailable.
 */
export function quotedPassage(ext: Pick<Extension, "references" | "passages">): Passage | null {
  for (const line of ext.references) {
    const found = ext.passages.find((p) => p.citation === line);
    if (found) return found;
  }
  return null;
}

export function firstName(name: string): string {
  return name.trim().split(/\s+/)[0] || "the patient";
}

/** The index of the next alert still to review after `current`, wrapping round; null when none is left. */
export function nextToReview(alertIds: string[], decided: Set<string>, current: number): number | null {
  for (let step = 1; step <= alertIds.length; step++) {
    const i = (current + step) % alertIds.length;
    if (!decided.has(alertIds[i])) return i;
  }
  return null;
}

export type GuidelineQuote = {
  /** What is quoted: the key sentence, or the passage from its start. */
  text: string;
  citation: string;
  /** The whole passage, for "Show the whole passage". */
  whole: string;
  isKeySentence: boolean;
};

/**
 * The guideline line an alert shows. The backend's key sentence when it sends one, with the
 * citation of the passage it came from; otherwise the first passage the references name, quoted
 * from its start (owner, 2026-11-26). Null when no passage is cited.
 */
export function guidelineQuote(
  ext: Pick<Extension, "key_sentence" | "references" | "passages"> & { kind?: Extension["kind"] },
): GuidelineQuote | null {
  const key = ext.key_sentence?.trim();
  if (key) {
    // An AI alert quotes only a passage it cited: a passage it was shown but didn't cite is not its source.
    const from = ext.passages.find((p) => p.text.includes(key) && (ext.kind !== "ai" || ext.references.includes(p.citation ?? "")));
    if (from) return { text: key, citation: from.citation ?? "", whole: from.text, isKeySentence: true };
  }
  const p = quotedPassage(ext);
  return p ? { text: p.text, citation: p.citation ?? "", whole: p.text, isKeySentence: false } : null;
}

/** Over a patient value: "Rose today", or "John, 1 Oct 2024" when it was taken before the visit. */
export function valueHeading(name: string, valueDate: string, visitDate: string): string {
  return valueDate === visitDate ? `${firstName(name)} today` : `${firstName(name)}, ${longDate(valueDate)}`;
}

