"use client";

// The clinic day (Paper FINAL S1 board, S1b list): today's appointments from GET /api/clinic-day,
// grouped by where each visit is. One main button: "Continue review" on the first visit that
// needs you. The day and the view (board or list) live in the address, so they survive a reload;
// blue links above the date step to the clinic days around it (owner, 2026-11-27).
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { AppFrame } from "@/components/frame/app-frame";
import { StatusChip } from "@/components/frame/status";
import { errorText } from "@/lib/api/client";
import { shortDay } from "@/lib/dates";
import { appointmentLine, appointmentNote, dayHeadline, dayHref, nextForYou, type DayAppointment } from "@/lib/day";
import { DISCLAIMER } from "@/lib/demo";
import { useClinicDay, visitHref } from "@/lib/queries";
import { cn } from "@/lib/utils";

type Column = { state: DayAppointment["state"]; title: string; hint: string };

const COLUMNS: Column[] = [
  { state: "waiting", title: "Waiting", hint: "Not checked yet" },
  { state: "needs_you", title: "Needs you", hint: "Checked, not finalized" },
  { state: "done", title: "Done", hint: "Visit finalized" },
];

export function DayScreen() {
  const params = useSearchParams();
  const date = params.get("date");
  const list = params.get("view") === "list";
  const day = useClinicDay(date);
  const appointments = day.data?.appointments ?? [];
  const next = nextForYou(appointments);
  const [first, rest] = day.data
    ? dayHeadline(day.data.date, day.data.counts.booked, appointments.filter((a) => a.state === "needs_you").length)
    : ["", ""];

  return (
    <AppFrame disclaimer={DISCLAIMER}>
      <div className="flex w-75 shrink-0 flex-col gap-6">
        {day.data && <DaySteps previous={day.data.previous_date ?? null} next={day.data.next_date ?? null} list={list} />}
        <h1 className="text-34 font-semibold tracking-[-0.025em] text-black">
          {first} <span className="text-muted-foreground">{rest}</span>
        </h1>
        <p className="text-15 leading-6 text-ink-2">
          {list
            ? "Your day runs top to bottom. Open a patient to work on one visit at a time."
            : "Where everyone is, at a glance. Switch to List to see your day top to bottom."}
        </p>
        <nav aria-label="View" className="flex w-50 gap-0.5 rounded-btn bg-fill p-[3px]">
          <ViewLink href={dayHref(date, false)} on={!list} icon={<BoardIcon on={!list} />}>
            Board
          </ViewLink>
          <ViewLink href={dayHref(date, true)} on={list} icon={<ListIcon on={list} />}>
            List
          </ViewLink>
        </nav>
        <Link
          href="/cases/new"
          className="flex h-10.5 w-50 items-center justify-center gap-2 rounded-btn border border-line-strong text-15 font-medium text-black"
        >
          <span aria-hidden className="text-18">
            +
          </span>
          Add patient case
        </Link>
      </div>

      <div className="flex min-w-0 flex-1 flex-col">
        {day.isPending && <p className="text-muted-foreground">Loading the day…</p>}
        {day.isError && <p role="alert">{errorText(day.error)}</p>}
        {day.data && (list ? <DayList appointments={appointments} next={next} /> : <DayBoard appointments={appointments} next={next} />)}
      </div>
    </AppFrame>
  );
}

/** The clinic days just before and after the one shown, as links; a side with no day is empty. */
function DaySteps({ previous, next, list }: { previous: string | null; next: string | null; list: boolean }) {
  if (!previous && !next) return null;
  return (
    <nav aria-label="Other clinic days" className="flex h-5 justify-between text-15 leading-5 text-blue">
      {previous ? (
        <Link href={dayHref(previous, list)} className="hover:underline">
          <span aria-hidden>← </span>
          {shortDay(previous)}
        </Link>
      ) : (
        <span />
      )}
      {next && (
        <Link href={dayHref(next, list)} className="hover:underline">
          {shortDay(next)}
          <span aria-hidden> →</span>
        </Link>
      )}
    </nav>
  );
}

function ViewLink({ href, on, icon, children }: { href: string; on: boolean; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      aria-current={on ? "page" : undefined}
      className={cn(
        "flex h-9 flex-1 items-center justify-center gap-[7px] rounded-[8px] text-15",
        on ? "border border-line-strong bg-white font-semibold text-ink" : "font-medium text-ink-2",
      )}
    >
      {icon}
      {children}
    </Link>
  );
}

function BoardIcon({ on }: { on: boolean }) {
  const fill = on ? "var(--color-ink)" : "var(--color-muted-foreground)";
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden className="shrink-0">
      <rect x="0" y="1" width="3.5" height="12" rx="1" fill={fill} />
      <rect x="5.25" y="1" width="3.5" height="8" rx="1" fill={fill} />
      <rect x="10.5" y="1" width="3.5" height="10" rx="1" fill={fill} />
    </svg>
  );
}

function ListIcon({ on }: { on: boolean }) {
  const fill = on ? "var(--color-ink)" : "var(--color-muted-foreground)";
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden className="shrink-0">
      <rect x="0" y="2" width="14" height="2" rx="1" fill={fill} />
      <rect x="0" y="6" width="14" height="2" rx="1" fill={fill} />
      <rect x="0" y="10" width="14" height="2" rx="1" fill={fill} />
    </svg>
  );
}

/**
 * A visit's dot: hollow while waiting, grey once checked; the board's "Needs you" heading is blue
 * (S1), and the visit with the main button gets the dark ringed dot in the list (S1b).
 */
function StateDot({ state, current, heading }: { state: DayAppointment["state"]; current?: boolean; heading?: boolean }) {
  if (current) return <span aria-hidden className="size-3.5 shrink-0 rounded-full border-3 border-glow bg-button" />;
  return (
    <span
      aria-hidden
      className={cn(
        "size-2.5 shrink-0 rounded-full",
        state === "waiting" && "border-[1.5px] border-line-strong bg-white",
        state === "needs_you" && (heading ? "bg-blue" : "bg-line-strong"),
        state === "done" && "bg-line-strong",
      )}
    />
  );
}

function DayBoard({ appointments, next }: { appointments: DayAppointment[]; next: DayAppointment | null }) {
  return (
    <div className="flex w-full items-start gap-4">
      {COLUMNS.map((col) => {
        const items = appointments.filter((a) => a.state === col.state);
        return (
          <section key={col.state} aria-label={col.title} className="flex min-w-0 flex-1 flex-col gap-2">
            <div className={cn("flex h-10 shrink-0 items-center justify-between rounded-btn px-3.5", col.state === "needs_you" ? "bg-blue-wash" : "bg-fill")}>
              <span className="flex items-center gap-2">
                <StateDot state={col.state} heading />
                <span className="text-15 font-semibold text-ink">{col.title}</span>
                <span className={cn("text-14", col.state === "needs_you" ? "text-ink-2" : "text-muted-foreground")}>{items.length}</span>
              </span>
              <span className={cn("text-13", col.state === "needs_you" ? "text-ink-2" : "text-muted-foreground")}>{col.hint}</span>
            </div>
            <ul className="flex flex-col gap-2">
              {items.map((a) => (
                <li key={a.patient_id}>
                  {a === next ? <CurrentCard a={a} /> : <Card a={a} />}
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}

function Card({ a }: { a: DayAppointment }) {
  const note = appointmentNote(a);
  return (
    <Link
      href={visitHref(a.patient_id, a.visit_id)}
      className="flex flex-col gap-2.5 rounded-[12px] border border-line bg-white px-3.5 py-3 hover:border-line-strong"
    >
      <span className="flex flex-col gap-[3px]">
        <span className="flex justify-between">
          <span className={cn("text-16 leading-5 font-medium", a.state === "done" ? "text-ink-2" : "text-black")}>{a.name}</span>
          <span className="text-14 leading-5 text-muted-foreground">{a.time}</span>
        </span>
        <span className="text-14 leading-[18px] text-muted-foreground">{appointmentLine(a)}</span>
      </span>
      {a.status && (
        <span className="flex items-center gap-2.5">
          <StatusChip state={a.status} />
          {note && <span className="text-14 leading-[18px] text-ink-2">{note}</span>}
        </span>
      )}
    </Link>
  );
}

/** The visit that needs you first (S1's Rose card): larger, with the screen's one main button. */
function CurrentCard({ a }: { a: DayAppointment }) {
  const note = appointmentNote(a);
  return (
    <div className="flex flex-col gap-3 rounded-[12px] border border-line-strong bg-surface p-4">
      <span className="flex flex-col gap-1">
        <span className="flex justify-between">
          <span className="text-18 leading-[22px] font-semibold tracking-[-0.01em] text-black">{a.name}</span>
          <span className="text-14 leading-[22px] font-semibold text-ink">{a.time}</span>
        </span>
        <span className="text-14 leading-[18px] text-ink-2">{appointmentLine(a)}</span>
      </span>
      {a.status && (
        <span className="flex items-center gap-2.5">
          <StatusChip state={a.status} />
          {note && <span className="text-14 leading-[18px] text-ink">{note}</span>}
        </span>
      )}
      <Link
        href={visitHref(a.patient_id, a.visit_id)}
        className="flex h-10.5 items-center justify-center rounded-btn bg-button text-15 font-semibold text-white"
      >
        Continue review
      </Link>
    </div>
  );
}

function DayList({ appointments, next }: { appointments: DayAppointment[]; next: DayAppointment | null }) {
  return (
    <ul aria-label="Today's visits" className="flex flex-col">
      {appointments.map((a) => {
        const current = a === next;
        const note = appointmentNote(a);
        const line = appointmentLine(a);
        const href = visitHref(a.patient_id, a.visit_id);
        return (
          <li
            key={a.patient_id}
            className={cn(
              "flex shrink-0 items-center",
              current ? "-ml-3.5 h-24 rounded-[12px] border border-line-strong bg-surface pr-4" : "border-b border-line",
              !current && (a.status ? "h-18" : "h-14"),
            )}
          >
            <span className={cn("w-16 shrink-0 text-14", current ? "pl-3 font-semibold text-ink" : "text-muted-foreground")}>{a.time}</span>
            <span className="flex w-7 shrink-0 justify-center">
              <StateDot state={a.state} current={current} />
            </span>
            <Link href={href} className={cn("flex min-w-0 flex-1 pl-3", a.status ? "flex-col gap-1" : "items-baseline gap-2.5")}>
              <span className={cn(current ? "text-18 leading-[22px] font-semibold tracking-[-0.01em]" : "text-16 leading-5 font-medium", a.state === "done" ? "text-ink-2" : "text-black")}>
                {a.name}
              </span>
              <span className={cn("text-14 leading-[18px]", current ? "text-ink-2" : "text-muted-foreground")}>
                {line}
                {a.state === "needs_you" && note && (
                  <>
                    {" · "}
                    <span className={current ? "text-ink" : undefined}>{note}</span>
                  </>
                )}
              </span>
            </Link>
            <span className="flex w-37.5 shrink-0">
              {a.status ? <StatusChip state={a.status} /> : <span className="text-14 text-muted-foreground">Not checked yet</span>}
            </span>
            <span className={cn("flex shrink-0 justify-end", current ? "w-46" : "w-50")}>
              {current ? (
                <Link href={href} className="flex h-10.5 items-center rounded-btn bg-button px-4.5 text-15 font-semibold text-white">
                  Continue review
                </Link>
              ) : a.state === "done" ? (
                <span className="text-14 text-muted-foreground">{note}</span>
              ) : (
                <Link href={href} className="text-14 text-ink-2">
                  Open
                </Link>
              )}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
