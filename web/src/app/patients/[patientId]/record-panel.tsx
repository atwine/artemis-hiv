// "From her record" (Paper FINAL S2): the record as recorded, one fact per row, and a way to see
// every lab result. Values and units are never converted (owner, 2026-11-26).
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { StatusShape } from "@/components/frame/status";
import { api, errorText, unwrap, type PatientDetail } from "@/lib/api/client";
import { clock, localDate, longDate } from "@/lib/dates";
import { visitHref } from "@/lib/queries";
import { labCount, labName, labRows, otherMedicines, possessive, previousArt, todaySummary } from "@/lib/record";
import { cn } from "@/lib/utils";

const NONE = "None recorded";

export function RecordPanel({ patient }: { patient: PatientDetail }) {
  const [full, setFull] = useState(false);
  const today = String(patient.today_encounter.date ?? "");
  const count = labCount(patient.labs);
  const title = `From ${possessive(patient.sex)} record`;

  return (
    <section aria-label={title} className="flex w-100 shrink-0 flex-col gap-3.5">
      <h2 className="text-13 font-semibold tracking-[0.06em] text-muted-foreground uppercase">{title}</h2>
      {full ? (
        <FullRecord patient={patient} />
      ) : (
        <dl className="flex flex-col">
          <Row label="Other medicines" text={otherMedicines(patient.other_medications) ?? NONE} />
          <Row label="Previous ART" text={previousArt(patient.regimen_history) ?? NONE} />
          {labRows(patient.labs, today).map((r) => (
            <Row key={r.label} label={r.label} text={r.text} />
          ))}
          {patient.lab_notes.map((n, i) => (
            <Row key={i} label="Lab notes" text={n.date ? `${n.text} (${longDate(n.date)})` : n.text} clamp />
          ))}
          <Row label="Today" text={todaySummary(patient.intake) ?? NONE} clamp />
        </dl>
      )}
      <button type="button" onClick={() => setFull(!full)} className="cursor-pointer self-start text-14 font-medium text-blue">
        {full ? (
          "Back to the summary"
        ) : (
          <>
            Full record{count > 0 ? `, ${count} lab ${count === 1 ? "result" : "results"}` : ""} <span aria-hidden>→</span>
          </>
        )}
      </button>
      <PastChecks patientId={patient.patient_id} />
    </section>
  );
}

function Row({ label, text, clamp }: { label: string; text: string; clamp?: boolean }) {
  return (
    <div className="flex border-b border-line py-[9px] text-14 leading-5">
      <dt className="w-32.5 shrink-0 text-muted-foreground">{label}</dt>
      <dd className={cn("min-w-0 text-black", clamp && "line-clamp-2")} title={clamp ? text : undefined}>
        {text}
      </dd>
    </div>
  );
}

const INTAKE: [key: string, label: string][] = [
  ["complaints_symptoms", "Complaints today"],
  ["examination_findings", "Examination"],
  ["prior_history", "History"],
];

/**
 * Everything the summary shortens: every lab result, one row per result (brief: "one row per
 * result"), the typed-in lab notes, and today's complaints, examination and history in full.
 */
function FullRecord({ patient }: { patient: PatientDetail }) {
  const rows = Object.entries(patient.labs).flatMap(([key, results]) =>
    [...results].sort((a, b) => b.date.localeCompare(a.date)).map((r) => ({ test: labName(key), ...r })),
  );
  return (
    <div className="flex flex-col gap-4">
      {rows.length > 0 && (
      <table aria-label="Lab results" className="w-full text-left text-14 leading-5">
        <thead className="text-muted-foreground">
          <tr className="border-b border-line">
            <th className="py-2 font-normal">Test</th>
            <th className="py-2 font-normal">Date</th>
            <th className="py-2 font-normal">Value</th>
            <th className="py-2 font-normal">Unit</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-b border-line text-black">
              <td className="py-2 pr-3">{r.test}</td>
              <td className="py-2 pr-3 whitespace-nowrap">{longDate(r.date)}</td>
              <td className="py-2 pr-3">{r.value}</td>
              <td className="py-2">{r.unit}</td>
            </tr>
          ))}
        </tbody>
      </table>
      )}
      {patient.lab_notes.map((n, i) => (
        <p key={i} className="text-14 leading-5 text-black">
          <span className="text-muted-foreground">Lab notes{n.date ? `, ${longDate(n.date)}` : ""}: </span>
          {n.text}
        </p>
      ))}
      {INTAKE.map(([key, label]) => {
        const text = patient.intake[key];
        return typeof text === "string" && text.trim() ? (
          <p key={key} className="text-14 leading-5 whitespace-pre-line text-black">
            <span className="text-muted-foreground">{label}: </span>
            {text.trim()}
          </p>
        ) : null;
      })}
    </div>
  );
}

/**
 * The patient's earlier checks, newest first (GET /api/patients/{id}/visits), each opening as saved.
 * In the record column, where the clinician already looks for history (owner, 2026-11-26).
 */
function PastChecks({ patientId }: { patientId: string }) {
  const past = useQuery({
    queryKey: ["past-checks", patientId],
    queryFn: async () => unwrap(await api.GET("/api/patients/{patient_id}/visits", { params: { path: { patient_id: patientId } } })),
    staleTime: 0,
  });
  return (
    <div className="mt-4 flex flex-col gap-2">
      <h3 className="text-13 font-semibold tracking-[0.06em] text-muted-foreground uppercase">Past checks</h3>
      {past.isError && <p className="text-14 text-ink-2">{errorText(past.error)}</p>}
      {past.data && past.data.length === 0 && <p className="text-14 text-ink-2">No earlier checks.</p>}
      {past.data && past.data.length > 0 && (
        <ul aria-label="Past checks" className="flex flex-col">
          {past.data.map((v) => (
            <li key={v.visit_id} className="border-b border-line">
              <Link href={visitHref(patientId, v.visit_id)} className="flex items-center gap-3 py-[9px] text-14 leading-5 hover:bg-surface">
                <span className="w-40 shrink-0 whitespace-nowrap text-muted-foreground">
                  {localDate(v.saved_at)}, {clock(v.saved_at)}
                </span>
                <span className="flex flex-1 items-center gap-1.5 text-black">
                  <StatusShape state={v.status} size={12} />
                  {v.status}
                </span>
                <span className="text-ink-2">{v.finalized_at ? "Finalized" : "Open"}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
