import Link from "next/link";
import { api } from "@/lib/api";
import type { AppRow, Intervention, Stats } from "@/lib/types";
import { Badge, ErrorBox, Stat } from "@/components/ui";
import { ago } from "@/lib/format";
import { runSearch } from "./actions";

type SP = { id: string; name: string; enabled: boolean; auto_apply: boolean; last_run_at: string | null };

export default async function Overview() {
  let stats: Stats, apps: AppRow[], ivs: Intervention[], sps: SP[];
  try {
    [stats, apps, ivs, sps] = await Promise.all([
      api<Stats>("/api/v1/stats"), api<AppRow[]>("/api/v1/applications?limit=10"),
      api<Intervention[]>("/api/v1/interventions"), api<SP[]>("/api/v1/search-profiles"),
    ]);
  } catch (e) {
    return <ErrorBox error={e} />;
  }
  const a = stats.applications;
  const sent = ["submitted", "acknowledged", "interviewing", "offer", "rejected", "ghosted"].reduce((n, k) => n + (a[k] ?? 0), 0);
  return (
    <div className="space-y-6">
      <h1>Overview</h1>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <Stat label="Needs you" value={stats.open_interventions} hint="answers, reviews, logins" />
        <Stat label="Shortlisted jobs" value={stats.matches.shortlisted ?? 0} hint={`${stats.open_jobs} open jobs tracked`} />
        <Stat label="Submitted" value={sent} hint={`${a.interviewing ?? 0} interviewing · ${a.offer ?? 0} offers`} />
        <Stat label="In flight" value={(a.queued ?? 0) + (a.in_progress ?? 0) + (a.needs_input ?? 0) + (a.ready_for_review ?? 0)} />
        <Stat label="LLM spend (24h)" value={`$${stats.llm_cost_24h.toFixed(2)}`} hint={`budget $${stats.llm_budget_24h} · total $${stats.llm_cost_total.toFixed(2)}`} />
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <section className="card">
          <h2>Needs your attention</h2>
          {ivs.length === 0 && <p className="text-sm text-slate-500">Nothing right now. Agents are working.</p>}
          <ul className="space-y-2">
            {ivs.slice(0, 8).map((i) => (
              <li key={i.id} className="flex items-center justify-between gap-2">
                <Link className="link text-sm" href={`/inbox/${i.id}`}>{i.title}</Link>
                <span className="text-xs text-slate-500">{ago(i.created_at)}</span>
              </li>
            ))}
          </ul>
        </section>
        <section className="card">
          <h2>Searches</h2>
          {sps.length === 0 && <p className="text-sm text-slate-500">No searches yet. <Link className="link" href="/settings">Create one in Settings</Link>.</p>}
          <ul className="space-y-2">
            {sps.map((sp) => (
              <li key={sp.id} className="flex items-center justify-between gap-2 text-sm">
                <span>{sp.name} {sp.auto_apply && <Badge tone="in_progress">auto-apply</Badge>} <span className="text-xs text-slate-500">ran {ago(sp.last_run_at)}</span></span>
                <form action={runSearch}><input type="hidden" name="id" value={sp.id} /><button className="btn-secondary">Run now</button></form>
              </li>
            ))}
          </ul>
        </section>
      </div>

      <section className="card">
        <h2>Recent applications</h2>
        <table className="table">
          <thead><tr><th>Job</th><th>State</th><th>Updated</th></tr></thead>
          <tbody>
            {apps.map((r) => (
              <tr key={r.id}>
                <td><Link className="link" href={`/applications/${r.id}`}>{r.title}</Link> <span className="text-slate-500">· {r.company}</span></td>
                <td><Badge tone={r.state}>{r.state.replaceAll("_", " ")}</Badge></td>
                <td className="text-slate-500">{ago(r.updated_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
