import Link from "next/link";
import { api } from "@/lib/api";
import type { AppRow } from "@/lib/types";
import { Badge, Empty, ErrorBox } from "@/components/ui";
import { ago } from "@/lib/format";

const FILTERS = [["", "All"], ["queued,in_progress,needs_input,ready_for_review,submitting", "In flight"],
  ["submitted,acknowledged,uncertain", "Submitted"], ["interviewing,offer", "Interviews & offers"], ["failed,expired,skipped,cancelled", "Stopped"]] as const;

export default async function Applications({ searchParams }: { searchParams: Promise<{ state?: string }> }) {
  const { state = "" } = await searchParams;
  let rows: AppRow[];
  try {
    rows = await api<AppRow[]>(`/api/v1/applications?state=${state}`);
  } catch (e) {
    return <ErrorBox error={e} />;
  }
  return (
    <div className="space-y-4">
      <h1>Applications</h1>
      <div className="flex flex-wrap gap-2">
        {FILTERS.map(([k, label]) => (
          <Link key={label} href={`/applications?state=${k}`} className={`rounded-full px-3 py-1 text-sm ${state === k ? "bg-indigo-600 text-white" : "bg-slate-200 dark:bg-slate-800"}`}>{label}</Link>
        ))}
      </div>
      {rows.length === 0 ? <Empty>No applications yet.</Empty> : (
        <div className="card overflow-x-auto">
          <table className="table">
            <thead><tr><th>Job</th><th>Company</th><th>State</th><th>ATS</th><th>Submitted</th><th>Updated</th></tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td><Link className="link" href={`/applications/${r.id}`}>{r.title}</Link>{r.error && <div className="text-xs text-rose-600">{r.error.slice(0, 120)}</div>}</td>
                  <td>{r.company}</td>
                  <td><Badge tone={r.state}>{r.state.replaceAll("_", " ")}</Badge></td>
                  <td>{r.ats}</td>
                  <td className="text-slate-500">{ago(r.submitted_at)}</td>
                  <td className="text-slate-500">{ago(r.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
