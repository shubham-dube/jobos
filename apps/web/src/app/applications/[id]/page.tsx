import { api, apiFileUrl } from "@/lib/api";
import { Badge, ErrorBox } from "@/components/ui";
import { ago, show } from "@/lib/format";
import { cancelApplication, retryApplication } from "../../actions";

type Field = { key: string; label: string; type: string; required: boolean };
type Detail = {
  id: string; state: string; attempt: number; error: string; gate: { action?: string; rule?: string; problems?: string[] };
  submitted_at: string | null; llm_cost_usd: number; job: { title: string; company: string; url: string } | null;
  events: { from: string; to: string; actor: string; data: Record<string, unknown>; at: string }[];
  pages: { attempt: number; page_index: number; url: string; page: { fields: Field[]; kind: string };
    plan: { values: { key: string; value: unknown; source: string; confidence: number; source_ref: string }[] } | null;
    fill_result: { results: { key: string; ok: boolean; error: string }[] } | null; screenshots: string[] }[];
  emails: { subject: string; from: string; category: string; received_at: string; summary: string }[];
};

export default async function ApplicationDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let d: Detail;
  try {
    d = await api<Detail>(`/api/v1/applications/${id}`);
  } catch (e) {
    return <ErrorBox error={e} />;
  }
  const running = ["queued", "in_progress", "needs_input", "ready_for_review"].includes(d.state);
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="mb-0">{d.job?.title}</h1><span className="text-slate-500">{d.job?.company}</span>
        <Badge tone={d.state}>{d.state.replaceAll("_", " ")}</Badge>
        <span className="text-xs text-slate-500">attempt {d.attempt} · LLM ${d.llm_cost_usd.toFixed(3)}</span>
        <div className="ml-auto flex gap-2">
          {d.job && <a className="btn-secondary" href={d.job.url} target="_blank" rel="noreferrer">Posting ↗</a>}
          {running ? <form action={cancelApplication}><input type="hidden" name="id" value={d.id} /><button className="btn-danger">Cancel</button></form>
            : <form action={retryApplication}><input type="hidden" name="id" value={d.id} /><button className="btn-secondary">Retry</button></form>}
        </div>
      </div>
      {d.error && <div className="card text-sm text-rose-700 dark:text-rose-300">{d.error}</div>}
      {d.gate?.rule && <div className="text-sm text-slate-500">Submit gate: {d.gate.action} (rule: {d.gate.rule}) {d.gate.problems?.join("; ")}</div>}

      <section className="card">
        <h2>Evidence: what was filled</h2>
        {d.pages.filter((p) => p.plan).map((p) => {
          const labels = Object.fromEntries(p.page.fields.map((f) => [f.key, f.label]));
          const results = Object.fromEntries((p.fill_result?.results ?? []).map((r) => [r.key, r]));
          return (
            <div key={`${p.attempt}-${p.page_index}-${p.url}`} className="mb-4">
              <div className="mb-1 text-xs text-slate-500">Attempt {p.attempt} · page {p.page_index + 1} · {p.url}</div>
              <table className="table">
                <thead><tr><th>Field</th><th>Value</th><th>Source</th><th>Check</th></tr></thead>
                <tbody>
                  {p.plan!.values.map((v) => (
                    <tr key={v.key}>
                      <td className="max-w-xs">{labels[v.key] ?? v.key}</td>
                      <td className="max-w-md whitespace-pre-wrap break-words">{show(v.value)}</td>
                      <td><Badge tone={v.source === "generated" ? "needs_input" : undefined}>{v.source}</Badge> <span className="text-xs text-slate-500">{Math.round(v.confidence * 100)}%</span></td>
                      <td>{results[v.key] ? (results[v.key].ok ? "✓" : <span className="text-rose-600">✕ {results[v.key].error}</span>) : ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        })}
      </section>

      <section className="card">
        <h2>Screenshots</h2>
        <div className="grid gap-3 md:grid-cols-3">
          {d.pages.flatMap((p) => p.screenshots).map((s) => (
            <a key={s} href={apiFileUrl(s)} target="_blank" rel="noreferrer">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={apiFileUrl(s)} alt="page screenshot" className="max-h-72 w-full rounded border object-cover object-top" />
            </a>
          ))}
        </div>
      </section>

      <div className="grid gap-4 md:grid-cols-2">
        <section className="card">
          <h2>Timeline</h2>
          <ol className="space-y-1 text-sm">
            {d.events.map((e, i) => (
              <li key={i}><span className="text-slate-500">{ago(e.at)}</span> · {e.from || "∅"} → <b>{e.to}</b> <span className="text-xs text-slate-500">({e.actor})</span></li>
            ))}
          </ol>
        </section>
        <section className="card">
          <h2>Emails</h2>
          {d.emails.length === 0 && <p className="text-sm text-slate-500">No related emails yet.</p>}
          <ul className="space-y-2 text-sm">{d.emails.map((e, i) => <li key={i}><Badge>{e.category}</Badge> {e.subject} <div className="text-xs text-slate-500">{e.summary}</div></li>)}</ul>
        </section>
      </div>
    </div>
  );
}
