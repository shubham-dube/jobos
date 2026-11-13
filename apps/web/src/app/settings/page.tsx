import { api } from "@/lib/api";
import { Badge, ErrorBox } from "@/components/ui";
import { ago } from "@/lib/format";
import { addMailbox, createRunner, revokeRunner, saveSearchProfile, saveSettingsJson } from "../actions";

type SP = { id: string; name: string; enabled: boolean; auto_apply: boolean; schedule_minutes: number; filters: Record<string, unknown>; last_run_at: string | null };
type Runner = { id: string; name: string; version: string; os: string; online: boolean; revoked: boolean; last_seen_at: string | null };
type Mailbox = { id: string; label: string; host: string; username: string; last_sync_at: string | null; last_error: string };

const DEFAULT_FILTERS = {
  keywords_any: ["engineer", "developer", "sde", "swe"],
  keywords_none: ["sales", "account executive", "recruiter"],
  countries: ["IN", "US", "GB", "CH", "AU", "NZ", "IE", "DE", "NL", "CA", "SG", "AE"],
  include_remote: true, remote_only: false, exclude_companies: [], seniority_max: "mid",
  require_visa_friendly_abroad: true, posted_within_days: 45, sources: ["greenhouse", "lever", "ashby"],
};

const EXAMPLE_RULE = {
  name: "trusted ATS, no AI-written text",
  when: { ats_in: ["greenhouse", "lever", "ashby"], min_match_score: 75, min_legitimacy: 70, max_generated_fields: 0,
    answer_sources_subset_of: ["profile", "preset", "answer_bank", "recipe", "user", "document"] },
  action: "auto_submit",
};

export default async function SettingsPage({ searchParams }: { searchParams: Promise<{ runner_token?: string }> }) {
  const { runner_token } = await searchParams;
  let settings: Record<string, unknown>, sps: SP[], runners: Runner[], mailboxes: Mailbox[];
  try {
    [settings, sps, runners, mailboxes] = await Promise.all([api<Record<string, unknown>>("/api/v1/settings"), api<SP[]>("/api/v1/search-profiles"),
      api<Runner[]>("/api/v1/runners"), api<Mailbox[]>("/api/v1/mailboxes")]);
  } catch (e) {
    return <ErrorBox error={e} />;
  }
  return (
    <div className="space-y-6">
      <h1>Settings</h1>

      <section className="card space-y-3">
        <h2>Searches</h2>
        {[...sps, null].map((sp) => (
          <form key={sp?.id ?? "new"} action={saveSearchProfile} className="space-y-2 border-b border-slate-200 pb-4 last:border-0 dark:border-slate-800">
            <input type="hidden" name="id" value={sp?.id ?? ""} />
            <div className="flex flex-wrap items-center gap-3">
              <input name="name" className="input w-64" defaultValue={sp?.name ?? ""} placeholder={sp ? "" : "New search name"} />
              <label className="flex items-center gap-1 text-sm"><input type="checkbox" name="enabled" defaultChecked={sp?.enabled ?? true} /> enabled</label>
              <label className="flex items-center gap-1 text-sm"><input type="checkbox" name="auto_apply" defaultChecked={sp?.auto_apply ?? false} /> auto-queue applications for shortlisted jobs</label>
              <label className="flex items-center gap-1 text-sm">every <input name="schedule_minutes" className="input w-20" defaultValue={sp?.schedule_minutes ?? 360} /> min</label>
              {sp && <span className="text-xs text-slate-500">last run {ago(sp.last_run_at)}</span>}
            </div>
            <textarea name="filters" className="input min-h-40 font-mono text-xs" defaultValue={JSON.stringify(sp?.filters ?? DEFAULT_FILTERS, null, 2)} />
            <button className="btn-secondary">{sp ? "Save" : "Create search"}</button>
          </form>
        ))}
      </section>

      <section className="card space-y-3">
        <h2>Autonomy, pacing & notifications</h2>
        <p className="text-sm text-slate-500">
          <b>approval_rules</b> decide what is submitted automatically; anything not matched goes to review (ADR-0015). Example rule:
        </p>
        <pre className="overflow-x-auto rounded bg-slate-100 p-2 text-xs dark:bg-slate-800">{JSON.stringify(EXAMPLE_RULE, null, 2)}</pre>
        <form action={saveSettingsJson} className="space-y-2">
          <textarea name="json" className="input min-h-96 font-mono text-xs" defaultValue={JSON.stringify(settings, null, 2)} />
          <button className="btn">Save settings</button>
        </form>
      </section>

      <section className="card space-y-3">
        <h2>Runners (your computer&apos;s browser)</h2>
        {runner_token && (
          <div className="rounded border border-amber-400 bg-amber-50 p-3 text-sm dark:bg-amber-900/20">
            New runner token (shown once): <code className="break-all">{runner_token}</code>
            <pre className="mt-2 overflow-x-auto text-xs">jobos-runner setup --api {process.env.JOBOS_PUBLIC_API_URL ?? "http://localhost:8000"} --token {runner_token}</pre>
          </div>
        )}
        <ul className="space-y-1 text-sm">
          {runners.map((r) => (
            <li key={r.id} className="flex items-center gap-2">
              <Badge tone={r.online ? "submitted" : r.revoked ? "failed" : undefined}>{r.revoked ? "revoked" : r.online ? "online" : "offline"}</Badge>
              {r.name} <span className="text-xs text-slate-500">{r.os} · v{r.version} · seen {ago(r.last_seen_at)}</span>
              {!r.revoked && <form action={revokeRunner} className="ml-auto"><input type="hidden" name="id" value={r.id} /><button className="text-xs text-rose-600">revoke</button></form>}
            </li>
          ))}
        </ul>
        <form action={createRunner} className="flex gap-2"><input name="name" className="input w-64" placeholder="e.g. windows-laptop" /><button className="btn-secondary">Create runner token</button></form>
      </section>

      <section className="card space-y-3">
        <h2>Mailboxes</h2>
        <ul className="space-y-1 text-sm">
          {mailboxes.map((m) => <li key={m.id}>{m.label} · {m.username} · {m.host} · synced {ago(m.last_sync_at)} {m.last_error && <span className="text-rose-600">{m.last_error}</span>}</li>)}
        </ul>
        <form action={addMailbox} className="flex flex-wrap gap-2">
          <input name="label" className="input w-32" placeholder="Label" required />
          <select name="provider" className="input w-40"><option value="gmail">Gmail</option><option value="zoho">Zoho (India)</option><option value="zoho_com">Zoho (global)</option><option value="outlook">Outlook</option></select>
          <input name="username" className="input w-64" placeholder="you@example.com" required />
          <input name="app_password" type="password" className="input w-48" placeholder="App password" required />
          <button className="btn-secondary">Connect</button>
        </form>
        <p className="text-xs text-slate-500">Uses IMAP with an app password (Gmail: Google Account → Security → App passwords; Zoho: My Account → Security → App passwords). Stored encrypted.</p>
      </section>
    </div>
  );
}
