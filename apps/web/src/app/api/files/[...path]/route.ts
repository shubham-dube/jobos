import { API_URL, TOKEN } from "@/lib/api";

export async function GET(_req: Request, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  const res = await fetch(`${API_URL}/api/v1/files/${path.map(encodeURIComponent).join("/")}`, {
    headers: { Authorization: `Bearer ${TOKEN}` }, cache: "no-store",
  });
  return new Response(res.body, { status: res.status, headers: { "Content-Type": res.headers.get("Content-Type") ?? "application/octet-stream" } });
}
