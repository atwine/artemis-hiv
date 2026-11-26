"use client";

import { useQuery } from "@tanstack/react-query";

import type { RailEntry } from "@/components/frame/day-rail";
import type { VisitState } from "@/components/frame/status";

import { api, unwrap } from "./api/client";

/** Today's appointments and each one's state. Always fresh: a check or a decision changes it. */
export function useClinicDay() {
  return useQuery({
    queryKey: ["clinic-day"],
    queryFn: async () => unwrap(await api.GET("/api/clinic-day")),
    staleTime: 0,
  });
}

/** Where a day's visit opens: the saved visit when its checks have run, else the patient. */
export function visitHref(patientId: string, visitId: string | null): string {
  const base = `/patients/${encodeURIComponent(patientId)}`;
  return visitId ? `${base}?visit=${encodeURIComponent(visitId)}` : base;
}

/**
 * The day rail: today's appointments by time, each with its status shape. The visit on screen
 * shows the state the caller passes (it may be checking right now).
 */
export function useRailEntries(current?: { id: string; state: VisitState }): RailEntry[] {
  const day = useClinicDay();
  return (day.data?.appointments ?? []).map((a) => ({
    id: a.patient_id,
    label: a.time,
    name: a.name,
    href: visitHref(a.patient_id, a.visit_id),
    state: a.patient_id === current?.id ? current.state : (a.status ?? "not_checked"),
  }));
}
