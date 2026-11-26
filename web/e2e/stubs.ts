// Stand-ins the screenshot test and the accessibility audit share. Each changes one API reply in the
// browser; nothing here calls a model.
import { execFileSync } from "node:child_process";
import path from "node:path";

import type { Page } from "@playwright/test";

import type { VisitCheck } from "../src/lib/api/client";

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
    await route.fulfill({ response: reply, json: day });
  });
}
