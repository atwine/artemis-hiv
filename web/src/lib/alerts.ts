// Plain functions for the alert screens: what each alert shows and where review goes next.
import type { Card } from "./api/client";

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
