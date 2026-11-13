import Link from "next/link";
import { api } from "@/lib/api";
import type { Intervention } from "@/lib/types";
import { Badge, Empty, ErrorBox } from "@/components/ui";
import { ago } from "@/lib/format";

export default async function Inbox() {
  let ivs: Intervention[];
  try {
    ivs = await api<Intervention[]>("/api/v1/interventions");
  } catch (e) {
    return <ErrorBox error={e} />;
  }
  return (
    <div className="space-y-4">
      <h1>Inbox</h1>
      {ivs.length === 0 && <Empty>Nothing needs you right now.</Empty>}
      {ivs.map((i) => (
        <Link key={i.id} href={`/inbox/${i.id}`} className="card block hover:border-indigo-400">
          <div className="flex items-center justify-between gap-2">
            <div><Badge tone="needs_input">{i.kind.replaceAll("_", " ")}</Badge> <span className="font-medium">{i.title}</span></div>
            <span className="text-xs text-slate-500">{ago(i.created_at)}</span>
          </div>
          {i.payload.questions && <div className="mt-1 text-sm text-slate-500">{i.payload.questions.map((q) => q.label).join(" · ").slice(0, 200)}</div>}
        </Link>
      ))}
    </div>
  );
}
