// Dates and clock times as the screens write them. Saved times come from the API in UTC and
// are shown on this computer's clock.

export const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2026-05-12" -> "12 May 2026"; anything else as it came. */
export function longDate(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return iso;
  return `${Number(m[3])} ${MONTHS[Number(m[2]) - 1]} ${m[1]}`;
}

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

/** "2026-11-24" -> "Tue 24 Nov": a calendar date (no time zone) as a short day name. */
export function shortDay(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  return `${WEEKDAYS[new Date(Date.UTC(y, m - 1, d)).getUTCDay()]} ${d} ${MONTHS[m - 1]}`;
}

/** "08:52", in this computer's time zone. */
export function clock(iso: string): string {
  const t = new Date(iso);
  return `${String(t.getHours()).padStart(2, "0")}:${String(t.getMinutes()).padStart(2, "0")}`;
}

/** "26 Nov 2026": a saved time's date in this computer's time zone (the same as clock()). */
export function localDate(iso: string): string {
  const t = new Date(iso);
  return `${t.getDate()} ${MONTHS[t.getMonth()]} ${t.getFullYear()}`;
}

/** Today on this computer's clock, as YYYY-MM-DD. */
export function todayIso(now: Date = new Date()): string {
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}
