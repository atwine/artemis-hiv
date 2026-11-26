"use client";

import { useQuery } from "@tanstack/react-query";

import type { RailEntry } from "@/components/frame/day-rail";
import type { VisitState } from "@/components/frame/status";

import { api, unwrap } from "./api/client";

export function usePatients() {
  return useQuery({ queryKey: ["patients"], queryFn: async () => unwrap(await api.GET("/api/patients")) });
}

/**
 * The day rail's entries. Until the backend serves the clinic day (times and each visit's state),
 * the rail lists the patients by id and shows every visit as not checked, except the one on
 * screen, whose state the caller passes.
 */
export function useRailEntries(current?: { id: string; state: VisitState }): RailEntry[] {
  const patients = usePatients();
  return (patients.data ?? []).map((p) => ({
    id: p.patient_id,
    label: p.patient_id,
    name: p.name,
    state: p.patient_id === current?.id ? current.state : "not_checked",
  }));
}
