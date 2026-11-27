// Compare plans (Paper FINAL S5): the AI's management plan next to the doctor's, as the API sends
// it. The plan's words are the API's, shown as sent; the headings, the waiting line and the line for
// a plan that couldn't be saved (the API sends no sentence for it) are the screen's.
// Owner, 2026-11-27: the AI's own note on the doctor's plan sits in its own column, "About your
// plan", in grey and without quote marks (it is the AI's sentence, not the note's); monitoring and
// counselling sit open under the table.
import { StatusShape, type VisitState } from "@/components/frame/status";
import { verdictMark, type ManagementPlan, type PlanItem } from "@/lib/plan";
import { asSentence } from "@/lib/record";
import { cn } from "@/lib/utils";

type Regimen = NonNullable<ManagementPlan["regimen"]>;

// The regimen badge in the alert colours, each with its shape (S5's "Switch").
const TONE: Record<Regimen["tone"], { shape: VisitState; className: string }> = {
  red: { shape: "RED", className: "bg-red-wash text-red" },
  amber: { shape: "AMBER", className: "bg-amber-wash text-amber" },
  green: { shape: "GREEN", className: "bg-mint text-green" },
  grey: { shape: "INCOMPLETE", className: "bg-fill text-grey" },
};

// Verdicts with no comparison behind them: the AI's note is left off, as the backend's own
// screen did (artemis/plan/view.py).
const NO_COMPARISON = new Set(["Not assessed", "No plan to compare"]);

export function PlanView({ plan, pending, error }: { plan: ManagementPlan | null; pending: boolean; error: string | null }) {
  return (
    <section aria-label="AI plan vs your plan" className="flex flex-col gap-6">
      {pending ? (
        <p className="text-15 text-ink-2">Making the AI&apos;s plan…</p>
      ) : (
        <>
          {error && (
            <p role="alert" className="text-15 text-red">
              {error}
            </p>
          )}
          {/* A refused retry leaves the plan before it on screen, under the refusal. */}
          {plan?.outcome === "failed" && (
            <p role={error ? undefined : "alert"} className="text-15 text-red">
              {plan.error}
            </p>
          )}
          {plan?.outcome === "made" && <MadePlan plan={plan} />}
        </>
      )}
    </section>
  );
}

function MadePlan({ plan }: { plan: ManagementPlan }) {
  const r = plan.regimen;
  return (
    <>
      {plan.issues_note && <p className="rounded-btn bg-amber-wash px-4 py-3 text-15 text-amber">{plan.issues_note}</p>}
      {!plan.saved && <p className="text-14 text-ink-2">This plan could not be saved.</p>}
      <div className="flex items-start gap-4">
        {r && (
          <span className={cn("flex h-8.5 shrink-0 items-center gap-[7px] rounded-chip px-3.5", TONE[r.tone].className)}>
            <StatusShape state={TONE[r.tone].shape} size={14} />
            <span className="text-15 font-bold">{r.label}</span>
          </span>
        )}
        <h2 className="text-24 font-semibold tracking-[-0.02em] text-black">
          AI plan vs your plan.
          {r && (
            <span className="text-muted-foreground">
              {" "}
              {r.tone === "grey" && r.text ? `${asSentence(r.text)} ` : ""}
              {r.reason}
            </span>
          )}
        </h2>
      </div>
      {plan.items.length > 0 && (
        <div role="table" aria-label="Each problem, the AI's plan and yours" className="flex flex-col">
          <div role="row" className="flex h-9 shrink-0 items-center border-b border-line text-13 leading-[21px] font-semibold tracking-[0.05em] text-muted-foreground uppercase">
            <span role="columnheader" className="w-62.5 shrink-0">Problem</span>
            <span role="columnheader" className="min-w-0 flex-1">AI suggests</span>
            <span role="columnheader" className="w-67.5 shrink-0">About your plan</span>
            <span role="columnheader" className="w-52.5 shrink-0">Verdict</span>
          </div>
          {plan.items.map((item, i) => (
            <Row key={i} item={item} />
          ))}
        </div>
      )}
      {(plan.monitoring.length > 0 || plan.counselling.length > 0) && (
        <div className="flex gap-12">
          <PlanList title="Monitoring" items={plan.monitoring} />
          <PlanList title="Counselling" items={plan.counselling} />
        </div>
      )}
    </>
  );
}

function Row({ item }: { item: PlanItem }) {
  const mark = verdictMark(item.verdict_label);
  return (
    <div role="row" className="flex min-h-14 items-center border-b border-line py-2 text-15 leading-[21px]">
      <span role="cell" className="w-62.5 shrink-0 pr-4 font-semibold text-black">
        {item.problem}
      </span>
      <span role="cell" className="min-w-0 flex-1 pr-4 text-black">
        {item.action}
      </span>
      <span role="cell" className="w-67.5 shrink-0 pr-4 text-ink-2">
        {NO_COMPARISON.has(item.verdict_label) ? "" : item.explanation}
      </span>
      <span role="cell" className={cn("w-52.5 shrink-0 text-black", item.verdict_label === "Differs from your plan" && "font-semibold")}>
        {mark && <span aria-hidden>{mark} </span>}
        {item.verdict_label}
      </span>
    </div>
  );
}

function PlanList({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  const id = `plan-${title.toLowerCase()}`;
  return (
    <div className="flex w-130 flex-col gap-2.5">
      <h3 id={id} className="text-18 font-semibold text-black">
        {title}
      </h3>
      <ul aria-labelledby={id} className="flex flex-col gap-2.5 text-15 leading-[21px] text-ink">
        {items.map((t, i) => (
          <li key={i}>{t}</li>
        ))}
      </ul>
    </div>
  );
}
