"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { api, errorText, unwrap } from "@/lib/api/client";

export default function PatientsPage() {
  const patients = useQuery({ queryKey: ["patients"], queryFn: async () => unwrap(await api.GET("/api/patients")) });

  return (
    <main>
      <h1>Patients</h1>
      {patients.isPending && <p>Loading patients…</p>}
      {patients.isError && <p role="alert">{errorText(patients.error)}</p>}
      {patients.data && (
        <ul>
          {patients.data.map((p) => (
            <li key={p.patient_id}>
              <Link href={`/patients/${encodeURIComponent(p.patient_id)}`}>
                {p.name} ({p.patient_id})
              </Link>{" "}
              · {p.age_years ?? "?"} {p.sex} · {p.art_regimen_current.join("/")} · visit {p.visit_date}
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
