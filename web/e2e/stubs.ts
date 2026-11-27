// Stand-ins the screenshot test and the accessibility audit share. Each changes one API reply in the
// browser; nothing here calls a model.
import { execFileSync } from "node:child_process";
import path from "node:path";

import type { Page } from "@playwright/test";

import type { VisitCheck } from "../src/lib/api/client";
import type { ManagementPlan } from "../src/lib/plan";

// The AI-review states the design doesn't draw (owner's decision 5). Each is a real reply to a
// rule-checks-only visit check (no model call), with the AI outcome, status and banners the API
// would send for it, computed by e2e/ai_states.py from the backend's own functions.
export type AiOutcome = "ok" | "search_unavailable" | "failed" | "unreadable" | "cut_off" | "partly_read";

export async function stubOutcome(page: Page, outcome: AiOutcome) {
  await page.route("**/api/patients/*/visits", async (route) => {
    if (route.request().method() !== "POST") return route.continue(); // only the check, not past checks
    const reply = await route.fetch();
    const body = (await reply.json()) as VisitCheck;
    const severities = JSON.stringify(body.cards.map((c) => c.extension.severity ?? null));
    const states = JSON.parse(
      execFileSync(process.env.PYTHON || "python", [path.join(__dirname, "ai_states.py"), severities], { encoding: "utf8" }),
    );
    const cards =
      outcome === "search_unavailable" // no search, so no guideline references (screen checklist)
        ? body.cards.map((c) => ({ ...c, extension: { ...c.extension, references: [], passages: [] } }))
        : body.cards;
    await route.fulfill({ response: reply, json: { ...body, ...states[outcome], ai_review: outcome, cards } });
  });
}

// The clinic day as the design draws it (S1, S1b): the real day from the API, with the design's
// states laid over it (two finalized, Rose needing review, one AI review failed).
export async function stubDesignDay(page: Page) {
  const DESIGN: Record<string, object> = {
    P004: { state: "done", visit_id: "v4", status: "GREEN", ai_review: "ok", finalized_at: "2026-11-26T06:52:00Z" },
    P003: { state: "done", visit_id: "v3", status: "AMBER", ai_review: "ok", alert_count: 1, reviewed_count: 1, finalized_at: "2026-11-26T07:18:00Z" },
    P005: { state: "needs_you", visit_id: "v5", status: "RED", ai_review: "ok", alert_count: 5, reviewed_count: 2 },
    P006: { state: "needs_you", visit_id: "v6", status: "INCOMPLETE", ai_review: "failed", ai_review_card_label: "AI review failed" },
  };
  await page.route("**/api/clinic-day", async (route) => {
    const reply = await route.fetch();
    const day = await reply.json();
    day.appointments = day.appointments.map((a: { patient_id: string }) => ({ ...a, ...(DESIGN[a.patient_id] ?? {}) }));
    Object.assign(day, { previous_date: "2026-11-24", next_date: "2026-11-27" }); // the days around it in S1
    await route.fulfill({ response: reply, json: day });
  });
}

// A management plan as Compare plans sends it (S5's own example), so no model is called; and the
// stand-in that answers POST /api/visits/{id}/plan with it (or a refusal). Returns the calls made.
export const PLAN: ManagementPlan = {
  visit_id: "stand-in",
  made_at: "2026-11-27T09:40:00Z",
  model: "stand-in",
  outcome: "made",
  regimen: { label: "Switch", tone: "red", text: "Switch", reason: "Substitute TDF with ABC (ABC/3TC/DTG) once viral load suppression is confirmed." },
  items: [
    { problem: "Kidney function falling on TDF", action: "Substitute TDF with ABC after confirming VL", reason: "eGFR fell.", verdict_label: "Differs from your plan", explanation: "Your plan continues TLD." },
    { problem: "Refill and review", action: "3-month refill, review in 3 months", reason: "Stable.", verdict_label: "Matches your plan", explanation: "Same refill and review." },
    { problem: "Weight", action: "Weigh at each visit", reason: "On DTG.", verdict_label: "Not assessed", explanation: "Something the screen leaves out." },
  ],
  monitoring: ["Viral load now, before any switch", "Creatinine and eGFR in 4-6 weeks"],
  counselling: ["Avoid ibuprofen; paracetamol for pain"],
  issues: [],
  issues_note: null,
  error: null,
  saved: true,
};

export async function standIn(page: Page, reply: { status?: number; json: object }) {
  const calls: string[] = [];
  await page.route("**/api/visits/*/plan", async (route) => {
    calls.push(route.request().url());
    await route.fulfill({ status: reply.status ?? 200, json: reply.json });
  });
  return calls;
}

// S5's own content, for the screenshot and the accessibility audit: the design's five problems,
// with the AI's notes as the owner chose to show them ("About your plan").
export const DESIGN_PLAN: ManagementPlan = {
  ...PLAN,
  items: [
    { problem: "Kidney function falling on TDF", action: "Substitute TDF with ABC after confirming VL", reason: "", verdict_label: "Differs from your plan", explanation: "Your plan continues TLD." },
    { problem: "Viral load before switching", action: "Repeat VL now (last May 2026)", reason: "", verdict_label: "Partly in your plan", explanation: "Notes VL suppressed; no repeat ordered." },
    { problem: "Ibuprofen", action: "Stop; paracetamol instead", reason: "", verdict_label: "Partly in your plan", explanation: "Adds paracetamol; ibuprofen not stopped." },
    { problem: "Kidney follow-up", action: "Repeat creatinine, eGFR, urine protein in 4–6 weeks", reason: "", verdict_label: "Not in your plan", explanation: "Kidney follow-up isn't mentioned." },
    { problem: "Refill and review", action: "3-month refill, review in 3 months", reason: "", verdict_label: "Matches your plan", explanation: "Same refill and review." },
  ],
  monitoring: ["Viral load now, before any switch", "Creatinine and eGFR in 4–6 weeks", "Urine protein at the next visit"],
  counselling: ["Why the switch waits for the viral load result", "Avoid ibuprofen; paracetamol for pain"],
};
