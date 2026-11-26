"use client";

import Link from "next/link";

import { AppFrame, PaneContent } from "@/components/frame/app-frame";
import { DayRail } from "@/components/frame/day-rail";
import { errorText } from "@/lib/api/client";
import { DISCLAIMER } from "@/lib/demo";
import { usePatients, useRailEntries } from "@/lib/queries";

// Today's patients. The clinic-day board (design S1) comes with the screens, once the backend
// serves the day's times and states; for now a plain list.
export default function PatientsPage() {
  const patients = usePatients();
  const rail = useRailEntries();

  return (
    <AppFrame rail={<DayRail entries={rail} />} disclaimer={DISCLAIMER}>
      <PaneContent>
        <h1 className="mb-4 text-20 font-semibold tracking-[-0.015em]">Today&apos;s patients</h1>
        {patients.isPending && <p className="text-muted">Loading patients…</p>}
        {patients.isError && <p role="alert">{errorText(patients.error)}</p>}
        {patients.data && (
          <ul className="max-w-3xl divide-y divide-line border-y border-line">
            {patients.data.map((p) => (
              <li key={p.patient_id} className="flex items-baseline gap-4 py-3">
                <Link href={`/patients/${encodeURIComponent(p.patient_id)}`} className="font-semibold text-ink underline-offset-2 hover:underline">
                  {p.name}
                </Link>
                <span className="text-muted">
                  {p.patient_id} · {p.age_years ?? "?"} {p.sex} · {p.art_regimen_current.join("/")}
                </span>
              </li>
            ))}
          </ul>
        )}
      </PaneContent>
    </AppFrame>
  );
}
