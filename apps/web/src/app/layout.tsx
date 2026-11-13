import type { Metadata } from "next";
import "./globals.css";
import { Nav } from "@/components/nav";
import { api } from "@/lib/api";
import type { Stats } from "@/lib/types";

export const metadata: Metadata = { title: "JobOS", description: "Your job search on autopilot" };
export const dynamic = "force-dynamic";

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  let open = 0;
  try {
    open = (await api<Stats>("/api/v1/stats")).open_interventions;
  } catch {}
  return (
    <html lang="en">
      <body>
        <Nav openInterventions={open} />
        <main className="mx-auto max-w-7xl px-4 py-6">{children}</main>
      </body>
    </html>
  );
}
