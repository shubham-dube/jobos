import { api } from "@/lib/api";
import { Badge, ErrorBox } from "@/components/ui";
import { show } from "@/lib/format";
import { addAnswer, deleteAnswer, deleteDocument, importProfile, saveProfileJson, uploadDocument } from "../actions";

type Doc = { id: string; kind: string; label: string; filename: string; is_default: boolean };
type Ans = { id: string; question: string; value: unknown; scope: string; scope_ref: string; source: string; use_count: number };
type Profile = { basics: { first_name: string; last_name: string; email: string; headline: string }; work: unknown[]; projects: unknown[]; skills: unknown[] };

export default async function ProfilePage() {
  let profile: Profile, docs: Doc[], answers: Ans[];
  try {
    [profile, docs, answers] = await Promise.all([api<Profile>("/api/v1/profile"), api<Doc[]>("/api/v1/documents"), api<Ans[]>("/api/v1/answers")]);
  } catch (e) {
    return <ErrorBox error={e} />;
  }
  return (
    <div className="space-y-6">
      <h1>Profile & answers</h1>
      <section className="card space-y-3">
        <h2>Master profile</h2>
        <p className="text-sm text-slate-500">
          {profile.basics.email ? <>{profile.basics.first_name} {profile.basics.last_name} · {profile.basics.email} · {profile.work.length} roles · {profile.projects.length} projects · {profile.skills.length} skills</> : "No profile yet — import one below."}
        </p>
        <form action={importProfile} className="space-y-2">
          <label className="label">Import from a resume (PDF) or paste your master profile document</label>
          <input type="file" name="file" accept=".pdf,.txt,.md" className="text-sm" />
          <textarea name="text" className="input min-h-32" placeholder="…or paste text / markdown here" />
          <button className="btn">Build profile with AI</button>
          <p className="text-xs text-slate-500">Creates a new profile version. The agent copies facts exactly and uses raw values (never &quot;alternative&quot; numbers).</p>
        </form>
        <details>
          <summary className="cursor-pointer text-sm text-indigo-600">Edit profile JSON</summary>
          <form action={saveProfileJson} className="mt-2 space-y-2">
            <textarea name="json" className="input min-h-[28rem] font-mono text-xs" defaultValue={JSON.stringify(profile, null, 2)} />
            <button className="btn">Save new version</button>
          </form>
        </details>
      </section>

      <section className="card space-y-3">
        <h2>Resumes</h2>
        <ul className="space-y-1 text-sm">
          {docs.map((d) => (
            <li key={d.id} className="flex items-center gap-2">
              <span>{d.filename}</span>{d.label && <Badge>{d.label}</Badge>}{d.is_default && <Badge tone="submitted">default</Badge>}
              <form action={deleteDocument} className="ml-auto"><input type="hidden" name="id" value={d.id} /><button className="text-xs text-rose-600">delete</button></form>
            </li>
          ))}
        </ul>
        <form action={uploadDocument} className="flex flex-wrap items-center gap-2">
          <input type="file" name="file" accept=".pdf,.doc,.docx" required className="text-sm" />
          <input name="label" className="input w-48" placeholder="Label, e.g. Backend" />
          <label className="flex items-center gap-1 text-sm"><input type="checkbox" name="is_default" /> default</label>
          <button className="btn-secondary">Upload</button>
        </form>
        <p className="text-xs text-slate-500">The matcher picks the best-fitting variant (by label) for each job.</p>
      </section>

      <section className="card space-y-3">
        <h2>Answer bank <span className="text-sm font-normal text-slate-500">({answers.length})</span></h2>
        <form action={addAnswer} className="flex flex-wrap gap-2">
          <input name="question" className="input flex-1" placeholder="Question, e.g. What is your notice period?" required />
          <input name="value" className="input w-64" placeholder="Answer" required />
          <button className="btn-secondary">Add</button>
        </form>
        <table className="table">
          <thead><tr><th>Question</th><th>Answer</th><th>Scope</th><th>Used</th><th /></tr></thead>
          <tbody>
            {answers.map((a) => (
              <tr key={a.id}>
                <td>{a.question}</td><td className="whitespace-pre-wrap">{show(a.value)}</td>
                <td><Badge>{a.scope}{a.scope_ref ? `: ${a.scope_ref}` : ""}</Badge></td><td>{a.use_count}</td>
                <td><form action={deleteAnswer}><input type="hidden" name="id" value={a.id} /><button className="text-xs text-rose-600">delete</button></form></td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
