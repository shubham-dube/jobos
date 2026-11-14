import { API_URL, TOKEN } from "@/lib/api";

// Streams one of the candidate's documents (PDF) from the API; the token never reaches the browser.
export async function GET(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const res = await fetch(`${API_URL}/api/v1/documents/${encodeURIComponent(id)}/file`, {
    headers: { Authorization: `Bearer ${TOKEN}` }, cache: "no-store",
  });
  const headers = new Headers({ "Content-Type": res.headers.get("Content-Type") ?? "application/pdf" });
  const disposition = res.headers.get("Content-Disposition");
  if (disposition) headers.set("Content-Disposition", disposition.replace(/^attachment/, "inline"));
  return new Response(res.body, { status: res.status, headers });
}
