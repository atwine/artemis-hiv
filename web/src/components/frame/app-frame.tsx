// The frame every screen shares (Paper FINAL, "Day Rail with floating tray"): top bar, the day
// rail on the left, the visit pane, the floating tray, and the footer. Sized for 1366 x 768:
// 56 + body + 94 + 44, with the body taking what is left.
import Link from "next/link";

import { DEMO_CLINIC, DEMO_CLINICIAN } from "@/lib/demo";

export function AppFrame({
  rail,
  children,
  tray,
  disclaimer,
}: {
  rail: React.ReactNode;
  children: React.ReactNode;
  tray?: React.ReactNode;
  disclaimer: string;
}) {
  return (
    <div className="flex h-dvh min-h-[600px] flex-col overflow-hidden bg-bg">
      <TopBar />
      <div className="flex min-h-0 flex-1 gap-4 bg-surface pt-4 pr-6">
        {rail}
        <main className="flex min-w-0 flex-1 flex-col overflow-clip rounded-window border border-line bg-white shadow-window">
          {children}
        </main>
      </div>
      {tray && <div className="flex shrink-0 bg-surface pt-3 pr-10 pb-3.5 pl-27">{tray}</div>}
      <Footer disclaimer={disclaimer} />
    </div>
  );
}

function TopBar() {
  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-line px-8">
      <div className="flex items-center gap-3.5">
        <Link href="/" className="flex items-center gap-3.5" aria-label="ARTEMIS-HIV, today's patients">
          <span aria-hidden className="flex size-5.5 shrink-0 items-center justify-center rounded-logo bg-button">
            <span className="size-2 rounded-full bg-white" />
          </span>
          <span className="text-15 font-bold tracking-[-0.01em] text-black">ARTEMIS-HIV</span>
        </Link>
        <span className="text-14 text-muted-foreground">{DEMO_CLINIC}</span>
      </div>
      <div className="flex items-center gap-2.5">
        <span className="text-14 text-ink-2">{DEMO_CLINICIAN.name}</span>
        <span aria-hidden className="flex size-7 shrink-0 items-center justify-center rounded-full bg-fill text-11 font-semibold text-ink-2">
          {DEMO_CLINICIAN.initials}
        </span>
      </div>
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
export function PaneHeader({ title, meta, aside }: { title: string; meta: string; aside?: React.ReactNode }) {
  return (
    <div className="flex h-17 shrink-0 items-center justify-between border-b border-line px-8">
      <h1 className="text-20 font-semibold tracking-[-0.015em] text-black">
        {title} <span className="font-medium text-muted-foreground">{meta}</span>
      </h1>
      <div className="flex items-center gap-5">
        {aside}
        <Link href="/" className="text-14 font-medium text-ink-2">
          ← Back to day
        </Link>
      </div>
    </div>
  );
}

/** The pane's working area under the header; it scrolls on its own when it is too tall. */
export function PaneContent({ children }: { children: React.ReactNode }) {
  return <div className="min-h-0 flex-1 overflow-y-auto px-8 py-7">{children}</div>;
}
