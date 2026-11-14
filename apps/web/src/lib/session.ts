export const SESSION_COOKIE = "jobos_session";

export async function sessionValue(password: string): Promise<string> {
  const data = new TextEncoder().encode(`${password}:jobos-web-session`);
  const digest = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, "0")).join("");
}
