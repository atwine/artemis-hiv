// Plain functions for the clinic day (Paper FINAL S1/S1b): the headline, each card's note, and
// which visit carries the one main button.
import type { components } from "./api/schema";

export type DayAppointment = components["schemas"]["Appointment"];

const WORDS = ["none", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve"];

/** Numbers to twelve in words, as the design writes them; bigger ones as digits. */
function inWords(n: number): string {
  return n < WORDS.length ? WORDS[n] : String(n);
}

function capitalised(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

const DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** ["Thursday 26 Nov.", "Seven patients, one waiting on you."] (S1's headline). */
export function dayHeadline(isoDate: string, booked: number, needYou: number): [string, string] {
  const [y, m, d] = isoDate.split("-").map(Number);
  const day = new Date(Date.UTC(y, m - 1, d));
  const first = `${DAYS[day.getUTCDay()]} ${d} ${MONTHS[m - 1]}.`;
  const patients = `${capitalised(inWords(booked))} ${booked === 1 ? "patient" : "patients"}`;
  return [first, `${patients}, ${inWords(needYou)} waiting on you.`];
}

/** "08:52", in this computer's time zone. */
export function clock(iso: string): string {
  const t = new Date(iso);
  return `${String(t.getHours()).padStart(2, "0")}:${String(t.getMinutes()).padStart(2, "0")}`;
}

const AI_TROUBLE: Partial<Record<NonNullable<DayAppointment["ai_review"]>, string>> = {
  failed: "AI review failed",
  unreadable: "AI review failed",
  cut_off: "AI review incomplete",
  partly_read: "AI review incomplete",
  search_unavailable: "Guideline search unavailable",
};

/** The line under a card's status: alerts reviewed, the AI review's trouble, or when it was finalized. */
export function appointmentNote(a: DayAppointment): string | null {
  if (a.state === "done") return a.finalized_at ? `Finalized ${clock(a.finalized_at)}` : "Finalized";
  if (a.state !== "needs_you") return null;
  if (a.alert_count > 0) return `${a.reviewed_count} of ${a.alert_count} ${a.alert_count === 1 ? "alert" : "alerts"} reviewed`;
  return (a.ai_review && AI_TROUBLE[a.ai_review]) || "No alerts";
}

/** The visit the main button opens: the first, by time, that needs you. */
export function nextForYou(day: DayAppointment[]): DayAppointment | null {
  return day.find((a) => a.state === "needs_you") ?? null;
}

/** "Dr. A. Okello" -> "AO": the first letters of the name, titles left out. */
export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter((w) => w && !/^(dr|mr|mrs|ms|prof)\.?$/i.test(w))
    .map((w) => w[0].toUpperCase())
    .join("")
    .slice(0, 2);
}
