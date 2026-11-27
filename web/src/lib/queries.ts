"use client";

import { useQuery } from "@tanstack/react-query";

import type { RailEntry } from "@/components/frame/day-rail";
import type { VisitState } from "@/components/frame/status";

import { api, unwrap } from "./api/client";

/**
 * A clinic day's appointments and each one's state: the given date, else the API's default day
 * (today, or the latest day before it). Always fresh: a check or a decision changes it.
 */
export function useClinicDay(date: string | null = null) {
  return useQuery({
    queryKey: ["clinic-day", date],
    queryFn: async () => unwrap(await api.GET("/api/clinic-day", { params: { query: date ? { date } : {} } })),
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

/** The add-case form's pick lists (ART drugs and combinations, lab tests with units, visit types). */
export function useFormChoices() {
  return useQuery({
    queryKey: ["form-choices"],
    queryFn: async () => unwrap(await api.GET("/api/form-choices")),
    staleTime: Infinity,
  });
}
