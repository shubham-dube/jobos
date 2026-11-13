import Link from "next/link";
import { api } from "@/lib/api";
import type { JobRow } from "@/lib/types";
import { Badge, ErrorBox, Score } from "@/components/ui";
import { applyToJob } from "../../actions";

export default async function JobDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let j: JobRow;
  try {
    j = await api<JobRow>(`/api/v1/jobs/${id}`);
  } catch (e) {
    return <ErrorBox error={e} />;
  }
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="mb-0">{j.title}</h1><span className="text-slate-500">{j.company}</span><Score value={j.score} />
      </div>
      <div className="flex flex-wrap gap-2">
        <Badge>{j.ats}</Badge>{j.eligibility?.status && <Badge tone={j.eligibility.eligible ? "submitted" : "failed"}>{j.eligibility.status}</Badge>}
        <span className="text-sm text-slate-500">{j.locations?.join(" · ")}</span>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <div className="card md:col-span-2 whitespace-pre-wrap text-sm leading-relaxed">{j.description || "No description."}</div>
        <div className="space-y-4">
          <div className="card space-y-2 text-sm">
            {j.application ? <Link className="link" href={`/applications/${j.application.id}`}>Application: {j.application.state}</Link> :
              <form action={applyToJob}><input type="hidden" name="job_id" value={j.job_id} /><button className="btn w-full justify-center">Apply with JobOS</button></form>}
            <a className="btn-secondary w-full justify-center" href={j.apply_url} target="_blank" rel="noreferrer">Open posting ↗</a>
          </div>
          <div className="card text-sm"><h2>Why it fits</h2><ul className="list-disc pl-4">{j.reasons?.map((r) => <li key={r}>{r}</li>)}</ul></div>
          <div className="card text-sm"><h2>Gaps</h2><ul className="list-disc pl-4">{j.gaps?.map((r) => <li key={r}>{r}</li>)}</ul></div>
          <div className="card text-sm"><h2>Eligibility & legitimacy</h2>
            <ul className="list-disc pl-4">{[...(j.eligibility?.reasons ?? []), ...(j.legitimacy_reasons ?? [])].map((r) => <li key={r}>{r}</li>)}</ul></div>
        </div>
      </div>
    </div>
  );
}
