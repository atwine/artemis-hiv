// The backend, typed from its own OpenAPI schema (schema.d.ts, made by `npm run api:types`).
// The browser calls it directly; the backend lets in only this site's own address (ACCESS.md).
import createClient from "openapi-fetch";

import type { components, paths } from "./schema";

// Not a secret: it is the backend's address on this laptop.
export const API_URL = process.env.NEXT_PUBLIC_ARTEMIS_API_URL || "http://127.0.0.1:8000";

export const api = createClient<paths>({ baseUrl: API_URL });

type Schemas = components["schemas"];
export type PatientSummary = Schemas["PatientSummary"];
export type PatientDetail = Schemas["PatientDetail"];
export type VisitCheck = Schemas["VisitCheckResponse"];
export type Card = Schemas["Card"];
export type Banner = Schemas["Banner"];
export type DecisionIn = Schemas["DecisionIn"];
export type DecisionOut = Schemas["DecisionOut"];
export type Decisions = Schemas["DecisionsResponse"];

/** An API failure, with a message that is safe to show. */
export class ApiError extends Error {}

const GENERIC = "Something went wrong talking to the ARTEMIS server. Please try again.";

/**
 * The data of an openapi-fetch reply, or an ApiError. The backend's own `detail` strings are
 * short and generic ("No such patient."), so they are shown; anything else gets a generic line.
 */
export function unwrap<T>(reply: { data?: T; error?: unknown; response: Response }): T {
  if (reply.data !== undefined) return reply.data;
  const detail = (reply.error as { detail?: unknown } | undefined)?.detail;
  throw new ApiError(typeof detail === "string" ? detail : GENERIC);
}

export function errorText(err: unknown): string {
  return err instanceof ApiError ? err.message : GENERIC;
}
