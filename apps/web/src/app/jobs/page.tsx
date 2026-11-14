import Link from "next/link";
import { api } from "@/lib/api";
import type { JobRow } from "@/lib/types";
import { Badge, Empty, ErrorBox, Score } from "@/components/ui";
import { ago } from "@/lib/format";
import { applyToJob, feedbackJob, importJobUrl } from "../actions";

const TABS = [["shortlisted", "Shortlisted"], ["scored", "Scored"], ["new", "Not scored yet"], ["filtered", "Filtered out"], ["queued", "Queued"], ["all", "All"]] as const;

export default async function Jobs({ searchParams }: { searchParams: Promise<{ status?: string; q?: string; page?: string }> }) {
  const sp = await searchParams;
  const status = sp.status ?? "shortlisted";
  const page = Number(sp.page ?? 0);
  let data: { total: number; items: JobRow[] };
  try {
    data = await api(`/api/v1/jobs?status=${status}&q=${encodeURIComponent(sp.q ?? "")}&limit=50&offset=${page * 50}`);
  } catch (e) {
    return <ErrorBox error={e} />;
  }
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="mb-0">Jobs <span className="text-base font-normal text-slate-500">({data.total})</span></h1>
        <form action={importJobUrl} className="flex gap-2">
          <input name="url" className="input w-80" placeholder="Paste a job link (Greenhouse, Lever, Ashby, Workday, Google Forms…)" required />
          <button className="btn-secondary">Add</button>
        </form>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {TABS.map(([k, label]) => (
          <Link key={k} href={`/jobs?status=${k}`} className={`rounded-full px-3 py-1 text-sm ${status === k ? "bg-indigo-600 text-white" : "bg-slate-200 dark:bg-slate-800"}`}>{label}</Link>
        ))}
        <form className="ml-auto"><input type="hidden" name="status" value={status} /><input name="q" defaultValue={sp.q} className="input w-56" placeholder="Search title or company" /></form>
      </div>
      {data.items.length === 0 && <Empty>No jobs here yet. Run a search from the Overview page.</Empty>}
      <div className="space-y-2">
        {data.items.map((j) => (
          <div key={j.match_id} className="card flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <Score value={j.score} label="fit" />
                <Link href={`/jobs/${j.job_id}`} className="font-medium hover:underline">{j.title}</Link>
                <span className="text-slate-500">· {j.company}</span>
                <Badge>{j.ats}</Badge>
                {j.remote_type !== "unknown" && <Badge>{j.remote_type}</Badge>}
                {j.eligibility?.status && <Badge tone={j.eligibility.eligible ? "submitted" : "failed"}>{j.eligibility.status.replaceAll("_", " ")}</Badge>}
                {j.legitimacy !== null && <span title={j.legitimacy_reasons.join("\n")} className="text-xs text-slate-500">legit {j.legitimacy}</span>}
              </div>
              <div className="mt-1 text-xs text-slate-500">{j.locations.join(" · ") || "—"} · posted {ago(j.posted_at)} · {j.seniority}</div>
              {j.reasons.length > 0 && <div className="mt-1 text-sm">✓ {j.reasons.slice(0, 2).join(" · ")}</div>}
              {j.gaps.length > 0 && <div className="text-sm text-amber-700 dark:text-amber-400">△ {j.gaps.slice(0, 2).join(" · ")}</div>}
              {j.filter_reasons.length > 0 && <div className="text-xs text-slate-500">filtered: {j.filter_reasons.join("; ")}</div>}
            </div>
            <div className="flex shrink-0 items-center gap-2">
              {j.application ? (
                <Link href={`/applications/${j.application.id}`}><Badge tone={j.application.state}>{j.application.state.replaceAll("_", " ")}</Badge></Link>
              ) : (
                <form action={applyToJob}><input type="hidden" name="job_id" value={j.job_id} /><button className="btn">Apply</button></form>
              )}
              <form action={feedbackJob}>
                <input type="hidden" name="match_id" value={j.match_id} /><input type="hidden" name="feedback" value="down" /><input type="hidden" name="dismiss" value="1" />
                <button className="btn-secondary" title="Not interested">✕</button>
              </form>
              <a className="btn-secondary" href={j.url} target="_blank" rel="noreferrer">Open ↗</a>
            </div>
          </div>
        ))}
      </div>
      <div className="flex justify-between">
        {page > 0 ? <Link className="link" href={`/jobs?status=${status}&page=${page - 1}`}>← Previous</Link> : <span />}
        {(page + 1) * 50 < data.total && <Link className="link" href={`/jobs?status=${status}&page=${page + 1}`}>Next →</Link>}
      </div>
    </div>
  );
}
