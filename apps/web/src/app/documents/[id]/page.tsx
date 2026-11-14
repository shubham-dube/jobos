import Link from "next/link";
import { api } from "@/lib/api";
import type { DiffLine, DocDetail } from "@/lib/types";
import { Badge, ErrorBox } from "@/components/ui";

const STATUS: Record<DiffLine["status"], { label: string; tone?: string }> = {
  reworded: { label: "reworded", tone: "needs_input" },
  verbatim: { label: "verbatim" },
  kept_original: { label: "kept original", tone: "failed" },
};

export default async function DocumentPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let d: DocDetail;
  try {
    d = await api<DocDetail>(`/api/v1/documents/${id}`);
  } catch (e) {
    return <ErrorBox error={e} />;
  }
  const m = d.meta;
  const g = m.grounding;
  const bySection = new Map<string, DiffLine[]>();
  for (const line of m.diff ?? []) bySection.set(line.section, [...(bySection.get(line.section) ?? []), line]);
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="mb-0">{d.label}</h1>
        {d.job_id && <Link className="link text-sm" href={`/jobs/${d.job_id}`}>{m.job_title} ↗</Link>}
      </div>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <a className="btn" href={`/api/documents/${d.id}`} target="_blank" rel="noreferrer">Open PDF</a>
        {m.pages != null && <Badge>{m.pages} page{m.pages === 1 ? "" : "s"}</Badge>}
        {g && <><Badge tone="needs_input">{g.reworded} reworded</Badge><Badge>{g.verbatim} verbatim</Badge>
          {g.rejected > 0 && <Badge tone="failed">{g.rejected} rewording(s) rejected</Badge>}</>}
        {m.used_llm === false && <Badge tone="failed">keyword selection (no LLM)</Badge>}
      </div>
      {m.generator === "tailored_resume" && (
        <p className="text-sm text-slate-500">
          Every line comes from your master profile. Reworded lines passed the grounding check (no new numbers, tools,
          or role changes); anything that failed was replaced with your original text.
        </p>
      )}
      {m.keywords && m.keywords.length > 0 && (
        <div className="card text-sm"><h2>Posting keywords</h2><div className="flex flex-wrap gap-1">{m.keywords.map((k) => <Badge key={k}>{k}</Badge>)}</div></div>
      )}
      {[...bySection.entries()].map(([section, lines]) => (
        <div key={section} className="card space-y-3">
          <h2 className="capitalize">{section}</h2>
          {lines.map((l, i) => (
            <div key={i} className="space-y-1 border-b border-slate-100 pb-2 text-sm last:border-0">
              <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                <span className="font-medium text-slate-700">{l.item_name}</span>
                <Badge tone={STATUS[l.status].tone}>{STATUS[l.status].label}</Badge>
                <span>sources: {l.sources.join(", ")}</span>
              </div>
              <p>{l.final_text}</p>
              {l.status !== "verbatim" && l.source_text !== l.final_text && (
                <p className="text-xs text-slate-500 line-through decoration-slate-300">{l.source_text}</p>
              )}
              {l.reason && <p className="text-xs text-rose-600">{l.reason}</p>}
            </div>
          ))}
        </div>
      ))}
      {m.paragraphs && (
        <div className="card space-y-2 text-sm"><h2>Letter</h2>{m.paragraphs.map((p, i) => <p key={i}>{p}</p>)}</div>
      )}
      {m.dropped && m.dropped.length > 0 && (
        <div className="card text-sm"><h2>Sentences removed by the grounding check</h2>
          <ul className="list-disc pl-4 text-slate-500">{m.dropped.map((x) => <li key={x}>{x}</li>)}</ul></div>
      )}
      {g && (g.dropped_items.length > 0 || g.notes.length > 0) && (
        <div className="card text-sm space-y-2">
          {g.dropped_items.length > 0 && <><h2>Not on this page</h2><p className="text-slate-500">{g.dropped_items.join(" · ")}</p></>}
          {(m.trimmed ?? []).length > 0 && <p className="text-xs text-slate-500">Trimmed to fit: {m.trimmed!.join(", ")}</p>}
          {g.notes.map((n) => <p key={n} className="text-xs text-slate-500">{n}</p>)}
        </div>
      )}
    </div>
  );
}
