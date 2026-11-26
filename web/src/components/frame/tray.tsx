// The floating dark tray: where the visit is (Clinical notes, Checks, one dot per alert, Plan,
// Finalize), a one-line prompt, and the screen's one primary button.
import { cn } from "@/lib/cn";

export type Step = "todo" | "current" | "done";

export type TrayButton = {
  label: string;
  onClick?: () => void;
  /** Submit this form (its id) instead of calling onClick. */
  form?: string;
  /** Shown greyed with a lock; says why in the prompt. */
  locked?: boolean;
  disabled?: boolean;
};

export type TrayProps = {
  notes: Step;
  checks: Step;
  /** One dot per alert, in order. Empty before the checks have run. */
  alerts: Step[];
  plan: Step;
  finalize: Step;
  /** The prompt's first, bold sentence, and the rest. */
  lead: string;
  rest?: string;
  primary?: TrayButton;
  secondary?: TrayButton;
  /** Shown in place of the buttons, e.g. while the checks run. */
  status?: React.ReactNode;
};

export function Tray(props: TrayProps) {
  const { primary, secondary } = props;
  return (
    <section
      aria-label="Visit steps"
      className="flex h-17 flex-1 items-center justify-between gap-5 rounded-window bg-button pr-3 pl-5.5 shadow-tray"
    >
      <div className="flex items-center gap-4.5">
        <ol className="flex shrink-0 items-center gap-3" aria-label="Where you are">
          <MainStep label="Clinical notes" step={props.notes} />
          <MainStep label="Checks" step={props.checks} />
          {props.alerts.length > 0 && (
            <li className="flex items-center gap-[5px] rounded-[20px] bg-white/8 px-1.5 py-1">
              <ol className="contents" aria-label="Alerts">
                {props.alerts.map((step, i) => (
                  <AlertDot key={i} n={i + 1} step={step} />
                ))}
              </ol>
            </li>
          )}
          <TextStep label="Plan" step={props.plan} />
          <TextStep label="Finalize" step={props.finalize} />
        </ol>
        <span aria-hidden className="h-8 w-px shrink-0 bg-white/15" />
        <p className="text-15 leading-5 text-tray-text" aria-live="polite">
          <span className="font-semibold text-white">{props.lead}</span>
          {props.rest ? ` ${props.rest}` : ""}
        </p>
      </div>
      {props.status ?? (
        <div className="flex shrink-0 flex-row-reverse items-center gap-2.5">
          {primary && <TrayAction button={primary} kind="primary" />}
          {secondary && <TrayAction button={secondary} kind="secondary" />}
        </div>
      )}
    </section>
  );
}

const STEP_WORD: Record<Step, string> = { todo: "to do", current: "current step", done: "done" };

function MainStep({ label, step }: { label: string; step: Step }) {
  return (
    <li className="flex items-center gap-1.5" aria-current={step === "current" ? "step" : undefined}>
      <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden className="shrink-0">
        {step === "done" ? (
          <>
            <circle cx="7" cy="7" r="7" fill="var(--color-tray-done)" />
            <path d="M4 7.2l2 2 4-4.4" fill="none" stroke="var(--color-ink)" strokeWidth="1.8" />
          </>
        ) : (
          <circle cx="7" cy="7" r="7" fill={step === "current" ? "#fff" : "#ffffff33"} />
        )}
      </svg>
      <span
        className={cn(
          "text-13",
          step === "current" && "font-semibold text-white",
          step === "done" && "text-tray-label",
          step === "todo" && "text-tray-todo",
        )}
      >
        {label}
        <span className="sr-only">, {STEP_WORD[step]}</span>
      </span>
    </li>
  );
}

function TextStep({ label, step }: { label: string; step: Step }) {
  return (
    <li
      aria-current={step === "current" ? "step" : undefined}
      className={cn("text-13", step === "current" ? "font-semibold text-white" : "text-tray-todo")}
    >
      {step === "done" && (
        <span aria-hidden className="text-tray-done">
          ✓{" "}
        </span>
      )}
      {label}
      <span className="sr-only">, {STEP_WORD[step]}</span>
    </li>
  );
}

function AlertDot({ n, step }: { n: number; step: Step }) {
  return (
    <li
      aria-current={step === "current" ? "step" : undefined}
      className={cn(
        "flex size-6.5 shrink-0 items-center justify-center rounded-full text-13",
        step === "todo" && "border-[1.5px] border-muted text-tray-number",
        step === "current" && "bg-white font-bold text-ink",
        step === "done" && "bg-tray-done-wash",
      )}
    >
      {step === "done" ? (
        <svg width="12" height="12" viewBox="0 0 14 14" aria-hidden className="shrink-0">
          <path d="M3 7.2l2.6 2.6 5.4-5.8" fill="none" stroke="var(--color-green)" strokeWidth="2" />
        </svg>
      ) : (
        <span aria-hidden>{n}</span>
      )}
      <span className="sr-only">
        Alert {n}, {STEP_WORD[step]}
      </span>
    </li>
  );
}

function TrayAction({ button, kind }: { button: TrayButton; kind: "primary" | "secondary" }) {
  const locked = Boolean(button.locked);
  return (
    <button
      type={button.form ? "submit" : "button"}
      form={button.form}
      onClick={button.onClick}
      disabled={locked || button.disabled}
      className={cn(
        "flex h-11.5 items-center gap-2.5 rounded-btn text-15 leading-[18px]",
        kind === "primary" && !locked && "bg-white px-6 font-semibold text-ink disabled:opacity-60",
        kind === "primary" && locked && "bg-white/12 px-6 font-semibold text-tray-label",
        kind === "secondary" && "border border-white/25 px-5 font-medium text-white disabled:opacity-60",
      )}
    >
      {locked && (
        <svg width="14" height="16" viewBox="0 0 14 16" aria-hidden className="shrink-0">
          <rect x="1" y="7" width="12" height="8" rx="2" fill="var(--color-tray-label)" />
          <path d="M4 7V5a3 3 0 016 0v2" fill="none" stroke="var(--color-tray-label)" strokeWidth="1.8" />
        </svg>
      )}
      {button.label}
    </button>
  );
}
