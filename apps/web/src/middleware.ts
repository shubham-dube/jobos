import { NextResponse, type NextRequest } from "next/server";
import { SESSION_COOKIE, sessionValue } from "@/lib/session";

export async function middleware(req: NextRequest) {
  const password = process.env.JOBOS_WEB_PASSWORD;
  if (!password) return NextResponse.next(); // local dev without a password
  if (req.nextUrl.pathname.startsWith("/login")) return NextResponse.next();
  const cookie = req.cookies.get(SESSION_COOKIE)?.value;
  if (cookie && cookie === (await sessionValue(password))) return NextResponse.next();
  const url = req.nextUrl.clone();
  url.pathname = "/login";
  return NextResponse.redirect(url);
}

export const config = { matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"] };
