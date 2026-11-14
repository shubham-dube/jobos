import Link from "next/link";
import { api } from "@/lib/api";
import type { Intervention } from "@/lib/types";
import { Badge, Empty, ErrorBox, Score } from "@/components/ui";
import { bulkReview } from "../actions";

type Facts = {
  match_score?: number | null; generated_fields?: number; low_confidence_fields?: number;
  tailored_resume?: boolean; tailored_rephrased?: number; generated_cover_letter?: boolean; countries?: string[];
};

/** Review queue: everything waiting for "approve & submit", sorted best match first, approvable in bulk.
 * Each approved application still passes its own submit gate (caps, validation) when it resumes. */
export default async function ReviewPage({ searchParams }: { searchParams: Promise<{ sort?: string }> }) {
  const { sort = "score" } = await searchParams;
  let items: Intervention[];
  try {
    items = await api<Intervention[]>("/api/v1/interventions?kind=review_before_submit&limit=1000");
  } catch (e) {
    return <ErrorBox error={e} />;
  }
  const facts = (i: Intervention) => (i.payload.gate?.facts ?? {}) as Facts;
  const rows = [...items].sort((a, b) =>
    sort === "oldest" ? a.created_at.localeCompare(b.created_at)
      : (facts(b).match_score ?? 0) - (facts(a).match_score ?? 0));
  const clean = (i: Intervention) => (facts(i).generated_fields ?? 0) === 0 && (facts(i).low_confidence_fields ?? 0) === 0;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="mb-0">Review queue</h1>
        <span className="text-sm text-slate-500">{rows.length} waiting · {rows.filter(clean).length} with no AI-written answers</span>
        <span className="ml-auto text-sm">Sort: <Link className="link" href="/review?sort=score">best match</Link> · <Link className="link" href="/review?sort=oldest">oldest</Link></span>
      </div>
      {rows.length === 0 ? <Empty>Nothing to review. New applications appear here when they are filled and ready.</Empty> : (
        <form action={bulkReview} className="space-y-3">
          <div className="flex flex-wrap gap-2">
            <button name="decision" value="approve" className="btn">Approve &amp; submit selected</button>
            <button name="decision" value="reject" className="btn-secondary">Skip selected</button>
            <span className="self-center text-xs text-slate-500">Tip: rows without AI-written answers are pre-selected.</span>
          </div>
          <div className="card overflow-x-auto p-0">
            <table className="table">
              <thead><tr><th className="w-8"></th><th>Job</th><th>Match</th><th>Answers</th><th>Documents</th><th>Waiting since</th></tr></thead>
              <tbody>
                {rows.map((i) => {
                  const f = facts(i);
                  return (
                    <tr key={i.id}>
                      <td><input type="checkbox" name="ids" value={i.id} defaultChecked={clean(i)} aria-label={`select ${i.payload.job?.company}`} /></td>
                      <td>
                        <Link className="link font-medium" href={`/inbox/${i.id}`}>{i.payload.job?.title}</Link>
                        <div className="text-xs text-slate-500">{i.payload.job?.company}{f.countries?.length ? ` · ${f.countries.join(", ")}` : ""}</div>
                      </td>
                      <td><Score value={f.match_score ?? null} /></td>
                      <td className="space-x-1 whitespace-nowrap">
                        {(f.generated_fields ?? 0) > 0 && <Badge tone="needs_input">{f.generated_fields} AI-written</Badge>}
                        {(f.low_confidence_fields ?? 0) > 0 && <Badge tone="failed">{f.low_confidence_fields} low confidence</Badge>}
                        {clean(i) && <Badge tone="submitted">all from profile</Badge>}
                      </td>
                      <td className="space-x-1 whitespace-nowrap">
                        {f.tailored_resume ? <Badge tone="needs_input">tailored · {f.tailored_rephrased} reworded</Badge> : <Badge>resume</Badge>}
                        {f.generated_cover_letter && <Badge tone="needs_input">cover letter</Badge>}
                      </td>
                      <td className="whitespace-nowrap text-xs text-slate-500">{new Date(i.created_at).toLocaleString()}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </form>
      )}
    </div>
  );
}
