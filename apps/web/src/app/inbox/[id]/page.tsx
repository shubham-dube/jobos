import Link from "next/link";
import { api } from "@/lib/api";
import type { Intervention, Question } from "@/lib/types";
import { Badge, ErrorBox } from "@/components/ui";
import { show } from "@/lib/format";
import { answerIntervention } from "../../actions";

function QuestionInput({ q }: { q: Question }) {
  const name = `a:${q.key}`;
  const suggestion = q.suggestion === null || q.suggestion === undefined ? "" : String(q.suggestion);
  if (q.type === "file") {
    return <input type="file" name={`f:${q.key}`} accept=".pdf,.doc,.docx,.txt,.rtf" required className="text-sm" />;
  }
  if (q.type === "multiselect" && q.options.length) {
    return <div className="space-y-1">{q.options.map((o) => <label key={o} className="flex items-center gap-2 text-sm"><input type="checkbox" name={name} value={o} /> {o}</label>)}</div>;
  }
  if (q.options.length) {
    return (
      <select name={name} className="input" defaultValue={suggestion} required>
        <option value="" disabled>Choose…</option>
        {q.options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    );
  }
  if (q.type === "checkbox") {
    return <select name={name} className="input" defaultValue="true"><option value="true">Yes / I agree</option><option value="false">No</option></select>;
  }
  if (q.type === "textarea") return <textarea name={name} className="input min-h-28" defaultValue={suggestion} required />;
  return <input name={name} className="input" defaultValue={suggestion} required />;
}

export default async function InterventionPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let iv: Intervention;
  try {
    iv = await api<Intervention>(`/api/v1/interventions/${id}`);
  } catch (e) {
    return <ErrorBox error={e} />;
  }
  const job = iv.payload.job;
  const closed = iv.status !== "open";
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="needs_input">{iv.kind.replaceAll("_", " ")}</Badge><h1 className="mb-0">{iv.title}</h1>
      </div>
      {job && <p className="text-sm text-slate-500">{job.title} at {job.company} · <a className="link" href={job.url} target="_blank" rel="noreferrer">posting ↗</a>
        {iv.application_id && <> · <Link className="link" href={`/applications/${iv.application_id}`}>application</Link></>}</p>}
      {closed && <div className="card text-sm">This request is {iv.status}. Answer: <code>{JSON.stringify(iv.answer)}</code></div>}

      {!closed && iv.kind === "missing_answer" && (
        <form action={answerIntervention} className="card space-y-4">
          <input type="hidden" name="id" value={iv.id} /><input type="hidden" name="kind" value={iv.kind} />
          {iv.payload.questions?.map((q) => (
            <div key={q.key} className="space-y-1">
              <label className="block font-medium">{q.label}</label>
              {q.type === "file" && <input type="hidden" name={`l:${q.key}`} value={q.label} />}
              {q.reason && <p className="text-xs text-slate-500">{q.reason}</p>}
              <QuestionInput q={q} />
              {q.type === "file" ? (
                <p className="text-xs text-slate-500">Saved to your Documents and reused automatically for similar uploads.</p>
              ) : <select name={`r:${q.key}`} className="input w-auto text-xs" defaultValue="global">
                <option value="global">Remember for all applications</option>
                <option value="company">Remember for this company</option>
                <option value="job">Only this job</option>
                <option value="none">Don&apos;t remember</option>
              </select>}
            </div>
          ))}
          <button className="btn">Send answers</button>
        </form>
      )}

      {!closed && iv.kind === "review_before_submit" && (
        <div className="space-y-4">
          {iv.payload.pages?.map((p, i) => (
            <div key={i} className="card">
              <div className="mb-2 text-xs text-slate-500">Page {i + 1} · {p.url}</div>
              <table className="table"><tbody>
                {p.fields.map((f, j) => (
                  <tr key={j}><td className="w-1/3">{f.label}</td><td className="whitespace-pre-wrap">{show(f.value)}</td>
                    <td><Badge tone={f.source === "generated" ? "needs_input" : undefined}>{f.source}</Badge></td></tr>
                ))}
              </tbody></table>
            </div>
          ))}
          <form action={answerIntervention} className="flex gap-2">
            <input type="hidden" name="id" value={iv.id} /><input type="hidden" name="kind" value={iv.kind} />
            <button name="decision" value="approve" className="btn">Approve &amp; submit</button>
            <button name="decision" value="reject" className="btn-secondary">Skip this job</button>
          </form>
        </div>
      )}

      {!closed && iv.kind === "account_creation_consent" && (
        <form action={answerIntervention} className="card space-y-3">
          <input type="hidden" name="id" value={iv.id} /><input type="hidden" name="kind" value={iv.kind} />
          <p className="text-sm">{iv.payload.message}</p>
          <div className="flex gap-2">
            <button name="decision" value="approve" className="btn">Create account</button>
            <button name="decision" value="always" className="btn-secondary">Always allow</button>
            <button name="decision" value="reject" className="btn-secondary">No</button>
          </div>
        </form>
      )}

      {!closed && !["missing_answer", "review_before_submit", "account_creation_consent"].includes(iv.kind) && (
        <form action={answerIntervention} className="card space-y-3">
          <input type="hidden" name="id" value={iv.id} /><input type="hidden" name="kind" value={iv.kind} />
          <p className="text-sm">{iv.payload.message}</p>
          {iv.payload.url && <p className="text-xs text-slate-500">{iv.payload.url}</p>}
          <button className="btn">Done</button>
        </form>
      )}
    </div>
  );
}
