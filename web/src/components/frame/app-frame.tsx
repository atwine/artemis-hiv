"use client";

// The frame every screen shares (Paper FINAL, "Day Rail with floating tray"): top bar, the day
// rail on the left, the visit pane, the floating tray, and the footer. Sized for 1366 x 768:
// 56 + body + 94 + 44, with the body taking what is left. The clinic day (S1) has no rail or pane:
// its body is the page's own.
import Link from "next/link";

import { initials } from "@/lib/day";
import { useClinicDay } from "@/lib/queries";

export function AppFrame({
  rail,
  children,
  tray,
  disclaimer,
}: {
  /** The day rail and the visit pane; without one, the body is the page's own (the clinic day). */
  rail?: React.ReactNode;
  children: React.ReactNode;
  tray?: React.ReactNode;
  disclaimer: string;
}) {
  return (
    <div className="flex h-dvh min-h-[600px] flex-col overflow-hidden bg-bg">
      <TopBar />
      {rail ? (
        <div className="flex min-h-0 flex-1 gap-4 bg-surface pt-4 pr-6">
          {rail}
          <main className="flex min-w-0 flex-1 flex-col overflow-clip rounded-window border border-line bg-white shadow-window">
            {children}
          </main>
        </div>
      ) : (
        <main className="flex min-h-0 flex-1 gap-14 overflow-y-auto px-12 pt-10 pb-6">{children}</main>
      )}
      {tray && <div className="flex shrink-0 bg-surface pt-3 pr-10 pb-3.5 pl-27">{tray}</div>}
      <Footer disclaimer={disclaimer} />
    </div>
  );
}

/** The app, then the clinic and the clinician from the API (no logins yet: the demo day's). */
function TopBar() {
  const day = useClinicDay().data;
  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-line px-8">
      <div className="flex items-center gap-3.5">
        <Link href="/" className="flex items-center gap-3.5" aria-label="ARTEMIS-HIV, today's patients">
          <span aria-hidden className="flex size-5.5 shrink-0 items-center justify-center rounded-logo bg-button">
            <span className="size-2 rounded-full bg-white" />
          </span>
          <span className="text-15 font-bold tracking-[-0.01em] text-black">ARTEMIS-HIV</span>
        </Link>
        {day && <span className="text-14 text-muted-foreground">{`${day.clinic} · ${day.room}`}</span>}
      </div>
      {day && (
        <div className="flex items-center gap-2.5">
          <span className="text-14 text-ink-2">{day.clinician}</span>
          <span aria-hidden className="flex size-7 shrink-0 items-center justify-center rounded-full bg-fill text-11 font-semibold text-ink-2">
            {initials(day.clinician)}
          </span>
        </div>
      )}
    </header>
  );
}

function Footer({ disclaimer }: { disclaimer: string }) {
  return (
    <footer className="flex h-11 shrink-0 items-center justify-between border-t border-line bg-surface px-12 text-13 text-muted-foreground">
      <p>{disclaimer}</p>
      {/* The design's one "Shortcuts" link; there are no shortcuts yet, so it isn't a link yet. */}
      <span aria-hidden>Shortcuts</span>
    </footer>
  );
}

/** The visit pane's header row: the patient on the left, the status and the way back on the right. */
export function PaneHeader({
  title,
  meta,
  aside,
  back,
}: {
  title: string;
  meta: string;
  aside?: React.ReactNode;
  /** The way back; the clinic day unless the screen has its own (a form's Cancel). */
  back?: React.ReactNode;
}) {
  return (
    <div className="flex h-17 shrink-0 items-center justify-between border-b border-line px-8">
      <h1 className="text-20 font-semibold tracking-[-0.015em] text-black">
        {title} <span className="font-medium text-muted-foreground">{meta}</span>
      </h1>
      <div className="flex items-center gap-5">
        {aside}
        {back ?? (
          <Link href="/" className="text-14 font-medium text-ink-2">
            ← Back to day
          </Link>
        )}
      </div>
    </div>
  );
}

/** The pane's working area under the header; it scrolls on its own when it is too tall. */
export function PaneContent({ children }: { children: React.ReactNode }) {
  return <div className="min-h-0 flex-1 overflow-y-auto px-8 py-7">{children}</div>;
}
