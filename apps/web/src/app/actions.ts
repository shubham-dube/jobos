"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { api } from "@/lib/api";

function str(form: FormData, key: string): string {
  return String(form.get(key) ?? "").trim();
}

/** Same rules the server's taxonomy uses to pick a stored document for an upload field. */
function documentKind(label: string): string {
  if (/transcript|grade ?(card|sheet|report)|mark ?sheet|academic record/i.test(label)) return "transcript";
  if (/cover ?letter|motivation(al)? letter/i.test(label)) return "cover_letter";
  if (/resume|\bcv\b|curriculum/i.test(label)) return "resume";
  return "other";
}

export async function applyToJob(form: FormData) {
  const jobId = str(form, "job_id");
  const res = await api<{ application_id: string }>(`/api/v1/jobs/${jobId}/apply`, { method: "POST", json: {} });
  redirect(`/applications/${res.application_id}`);
}

export async function feedbackJob(form: FormData) {
  await api(`/api/v1/matches/${str(form, "match_id")}/feedback`, {
    method: "POST", json: { feedback: str(form, "feedback"), dismiss: str(form, "dismiss") === "1" },
  });
  revalidatePath("/jobs");
}

export async function importJobUrl(form: FormData) {
  const out = await api<{ job_id?: string }>("/api/v1/jobs/import-url", { method: "POST", json: { url: str(form, "url") } });
  revalidatePath("/jobs");
  if (out.job_id) redirect(`/jobs/${out.job_id}`); // single forms (Google Forms) open straight on the job page
}

export async function runSearch(form: FormData) {
  await api(`/api/v1/search-profiles/${str(form, "id")}/run?max_llm_scores=${str(form, "max") || "500"}`, { method: "POST" });
  revalidatePath("/");
}

export async function retryApplication(form: FormData) {
  await api(`/api/v1/applications/${str(form, "id")}/retry`, { method: "POST" });
  revalidatePath(`/applications/${str(form, "id")}`);
}

export async function cancelApplication(form: FormData) {
  await api(`/api/v1/applications/${str(form, "id")}/cancel`, { method: "POST" });
  revalidatePath(`/applications/${str(form, "id")}`);
}

export async function answerIntervention(form: FormData) {
  const id = str(form, "id");
  const kind = str(form, "kind");
  let body: Record<string, unknown> = {};
  if (kind === "review_before_submit" || kind === "account_creation_consent") body = { decision: str(form, "decision") };
  else if (kind === "missing_answer") {
    const answers: Record<string, unknown> = {};
    const remember: Record<string, string> = {};
    for (const [k, v] of form.entries()) {
      if (k.startsWith("a:")) {
        const key = k.slice(2);
        const value = String(v);
        if (answers[key] !== undefined) answers[key] = ([] as unknown[]).concat(answers[key], value);
        else answers[key] = value;
      }
      if (k.startsWith("r:")) remember[k.slice(2)] = String(v);
      if (k.startsWith("f:") && v instanceof File && v.size > 0) {
        // upload the file as a Document, then answer the question with a reference to it
        const key = k.slice(2);
        const label = str(form, `l:${key}`);
        const fd = new FormData();
        fd.set("file", v);
        fd.set("kind", documentKind(label));
        fd.set("label", label.slice(0, 120));
        fd.set("is_default", "true");
        const doc = await api<{ id: string }>("/api/v1/documents", { method: "POST", body: fd });
        answers[key] = `doc:${doc.id}`;
      }
    }
    body = { answers, remember };
  } else body = { done: true };
  await api(`/api/v1/interventions/${id}/answer`, { method: "POST", json: body });
  revalidatePath("/inbox");
  redirect("/inbox");
}

export async function bulkReview(form: FormData) {
  const ids = form.getAll("ids").map(String).filter(Boolean);
  const decision = str(form, "decision");
  if (ids.length) await api("/api/v1/interventions/bulk", { method: "POST", json: { ids, decision } });
  revalidatePath("/review");
  revalidatePath("/inbox");
  redirect("/review");
}

export async function tailorJob(form: FormData) {
  const jobId = str(form, "job_id");
  const out = await api<{ resume: { id: string } }>(`/api/v1/jobs/${jobId}/tailor`, {
    method: "POST", json: { force: form.get("force") === "1", cover_letter: form.get("cover_letter") === "1" },
  });
  revalidatePath(`/jobs/${jobId}`);
  redirect(`/documents/${out.resume.id}`);
}

export async function importProfile(form: FormData) {
  const fd = new FormData();
  const file = form.get("file");
  if (file instanceof File && file.size > 0) fd.set("file", file);
  else fd.set("text", str(form, "text"));
  await api("/api/v1/profile/import", { method: "POST", body: fd });
  revalidatePath("/profile");
}

export async function saveProfileJson(form: FormData) {
  await api("/api/v1/profile", { method: "PUT", json: JSON.parse(str(form, "json")) });
  revalidatePath("/profile");
}

export async function uploadDocument(form: FormData) {
  const fd = new FormData();
  fd.set("file", form.get("file") as File);
  fd.set("label", str(form, "label"));
  fd.set("kind", str(form, "kind") || "resume");
  fd.set("is_default", form.get("is_default") ? "true" : "false");
  await api("/api/v1/documents", { method: "POST", body: fd });
  revalidatePath("/profile");
}

export async function deleteDocument(form: FormData) {
  await api(`/api/v1/documents/${str(form, "id")}`, { method: "DELETE" });
  revalidatePath("/profile");
}

export async function addAnswer(form: FormData) {
  await api("/api/v1/answers", { method: "POST", json: { question: str(form, "question"), value: str(form, "value"), scope: "global" } });
  revalidatePath("/profile");
}

export async function deleteAnswer(form: FormData) {
  await api(`/api/v1/answers/${str(form, "id")}`, { method: "DELETE" });
  revalidatePath("/profile");
}

export async function saveSettingsJson(form: FormData) {
  await api("/api/v1/settings", { method: "PUT", json: JSON.parse(str(form, "json")) });
  revalidatePath("/settings");
}

export async function saveSearchProfile(form: FormData) {
  const id = str(form, "id");
  const body = {
    name: str(form, "name") || "My search",
    enabled: form.get("enabled") === "on",
    auto_apply: form.get("auto_apply") === "on",
    schedule_minutes: Number(str(form, "schedule_minutes") || 360),
    filters: JSON.parse(str(form, "filters") || "{}"),
  };
  if (id) await api(`/api/v1/search-profiles/${id}`, { method: "PUT", json: body });
  else await api("/api/v1/search-profiles", { method: "POST", json: body });
  revalidatePath("/settings");
}

export async function addMailbox(form: FormData) {
  await api("/api/v1/mailboxes", {
    method: "POST",
    json: { label: str(form, "label"), provider: str(form, "provider"), username: str(form, "username"), app_password: str(form, "app_password") },
  });
  revalidatePath("/settings");
}

export async function createRunner(form: FormData) {
  const res = await api<{ token: string }>("/api/v1/runners", { method: "POST", json: { name: str(form, "name") || "my-pc" } });
  redirect(`/settings?runner_token=${encodeURIComponent(res.token)}`);
}

export async function revokeRunner(form: FormData) {
  await api(`/api/v1/runners/${str(form, "id")}`, { method: "DELETE" });
  revalidatePath("/settings");
}
