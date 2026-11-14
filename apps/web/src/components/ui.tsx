import type { ReactNode } from "react";

const STATE_COLORS: Record<string, string> = {
  submitted: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
  acknowledged: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
  interviewing: "bg-violet-100 text-violet-800 dark:bg-violet-900/40 dark:text-violet-300",
  offer: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  needs_input: "bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300",
  ready_for_review: "bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300",
  in_progress: "bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-300",
  queued: "bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-300",
  submitting: "bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-300",
  failed: "bg-rose-100 text-rose-800 dark:bg-rose-900/40 dark:text-rose-300",
  rejected: "bg-rose-100 text-rose-800 dark:bg-rose-900/40 dark:text-rose-300",
  uncertain: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300",
};

export function Badge({ children, tone }: { children: ReactNode; tone?: string }) {
  const cls = (tone && STATE_COLORS[tone]) || "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300";
  return <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}>{children}</span>;
}

export function Score({ value, label }: { value: number | null | undefined; label?: string }) {
  if (value === null || value === undefined) return <span className="text-xs text-slate-400">—</span>;
  const tone = value >= 75 ? "bg-emerald-600" : value >= 60 ? "bg-sky-600" : value >= 40 ? "bg-amber-500" : "bg-slate-400";
  return (
    <span title={label} className={`inline-flex min-w-9 justify-center rounded-md px-1.5 py-0.5 text-xs font-semibold text-white ${tone}`}>
      {value}
    </span>
  );
}

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div className="card">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold">{value}</div>
      {hint && <div className="mt-1 text-xs text-slate-500">{hint}</div>}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="card text-center text-sm text-slate-500">{children}</div>;
}

export function ErrorBox({ error }: { error: unknown }) {
  const msg = error instanceof Error ? error.message : String(error);
  return (
    <div className="card border-rose-300 text-sm text-rose-700 dark:border-rose-800 dark:text-rose-300">
      Could not reach the JobOS API: {msg}. Is <code>jobos serve</code> running and are JOBOS_API_URL / JOBOS_API_TOKEN set?
    </div>
  );
}
