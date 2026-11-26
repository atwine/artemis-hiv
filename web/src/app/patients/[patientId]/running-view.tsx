// Checks running (Paper FINAL S3), kept honest: the API answers once, when every check is done,
// so no row says "done" early and nothing counts alerts before the answer. The seconds are real;
// the bar is time against the AI review's usual length, never progress the API reported.
import { useEffect, useState } from "react";

import type { PatientDetail } from "@/lib/api/client";
import { firstName } from "@/lib/alerts";
import { checkReads } from "@/lib/record";

/** The AI review's usual length (GLM 5.2 averaged 14 s in Phase 2; the design says about 15). */
export const AI_USUAL_SECONDS = 15;

/** Whole seconds since `startedAt`, ticking once a second. */
export function useElapsedSeconds(startedAt: number): number {
  const [now, setNow] = useState(startedAt);
  useEffect(() => {
    const tick = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(tick);
  }, []);
  return Math.max(0, Math.floor((now - startedAt) / 1000));
}

/** How far the bar reaches: elapsed time against the usual length, stopping short of the end. */
export function barShare(seconds: number): number {
  return Math.min(seconds / AI_USUAL_SECONDS, 0.95);
}

export function RunningView({ patient, aiReview, seconds }: { patient: PatientDetail; aiReview: boolean; seconds: number }) {
  return (
    <section aria-label="Checks running" className="flex flex-col gap-6">
      <h2 className="max-w-225 text-30 font-semibold tracking-[-0.025em] text-black">
        Checking {firstName(patient.name || "the patient")}&apos;s visit.{" "}
        <span className="text-muted-foreground">
          {aiReview ? `The AI review takes about ${AI_USUAL_SECONDS} seconds.` : "Rule checks only."}
        </span>
      </h2>
      <ul className="flex max-w-225 flex-col border-t border-line">
        <Row title="Rule checks" state="running" />
        {aiReview && <Row title="AI review" state="reading" seconds={seconds} />}
      </ul>
      <p className="max-w-225 text-15 leading-[18px] text-ink-2" aria-live="off">
        {checkReads(patient, aiReview)}
      </p>
    </section>
  );
}

function Row({ title, state, seconds }: { title: string; state: string; seconds?: number }) {
  return (
    <li className="flex min-h-21 items-center gap-4 border-b border-line py-4">
      <span aria-hidden className="size-5.5 shrink-0 animate-spin rounded-full border-2 border-line-strong border-t-blue motion-reduce:animate-none" />
      <div className="flex flex-1 flex-col gap-2">
        <p className="text-17 font-semibold text-black">
          {title} · {state}
          {seconds !== undefined && (
            <span className="font-medium text-muted-foreground">
              {" "}
              {seconds} s of about {AI_USUAL_SECONDS} s
            </span>
          )}
        </p>
        {seconds !== undefined && (
          <div className="h-1.5 w-full rounded-[3px] bg-blue-wash">
            <div className="h-1.5 rounded-[3px] bg-blue transition-[width] duration-1000 ease-linear" style={{ width: `${barShare(seconds) * 100}%` }} />
          </div>
        )}
      </div>
    </li>
  );
}

/** The running screen, counting its own seconds. */
export function Running({ patient, aiReview, startedAt }: { patient: PatientDetail; aiReview: boolean; startedAt: number }) {
  return <RunningView patient={patient} aiReview={aiReview} seconds={useElapsedSeconds(startedAt)} />;
}

/** The tray's right side while the checks run (S3): the seconds so far, and the same bar. */
export function RunningTrayStatus({ aiReview, startedAt }: { aiReview: boolean; startedAt: number }) {
  const seconds = useElapsedSeconds(startedAt);
  return (
    <div className="flex shrink-0 flex-col items-end gap-2 pr-2.5">
      <p className="text-14 leading-[18px] text-tray-text">
        <span className="font-semibold text-white">{seconds} s</span>
        {aiReview ? ` · AI review about ${AI_USUAL_SECONDS} s` : " · rule checks"}
      </p>
      {aiReview && (
        <div className="h-[5px] w-60 rounded-[3px] bg-white/15">
          <div className="h-[5px] rounded-[3px] bg-white transition-[width] duration-1000 ease-linear" style={{ width: `${barShare(seconds) * 100}%` }} />
        </div>
      )}
    </div>
  );
}
