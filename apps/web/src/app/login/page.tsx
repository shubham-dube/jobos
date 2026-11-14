import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { SESSION_COOKIE, sessionValue } from "@/lib/session";

async function login(form: FormData) {
  "use server";
  const password = process.env.JOBOS_WEB_PASSWORD ?? "";
  if (!password || form.get("password") !== password) redirect("/login?error=1");
  (await cookies()).set(SESSION_COOKIE, await sessionValue(password), {
    httpOnly: true, sameSite: "lax", secure: process.env.NODE_ENV === "production", maxAge: 60 * 60 * 24 * 30, path: "/",
  });
  redirect("/");
}

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ error?: string }> }) {
  const { error } = await searchParams;
  return (
    <form action={login} className="card mx-auto mt-24 max-w-sm space-y-3">
      <h1>Sign in</h1>
      <input className="input" type="password" name="password" placeholder="Dashboard password" autoFocus />
      {error && <p className="text-sm text-rose-600">Wrong password</p>}
      <button className="btn w-full justify-center">Sign in</button>
    </form>
  );
}
