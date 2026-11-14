import Link from "next/link";

const LINKS = [
  ["/", "Overview"],
  ["/inbox", "Inbox"],
  ["/review", "Review"],
  ["/jobs", "Jobs"],
  ["/applications", "Applications"],
  ["/profile", "Profile & answers"],
  ["/settings", "Settings"],
] as const;

export function Nav({ openInterventions }: { openInterventions: number }) {
  return (
    <nav className="sticky top-0 z-10 border-b border-slate-200 bg-white/90 backdrop-blur dark:border-slate-800 dark:bg-slate-950/90">
      <div className="mx-auto flex max-w-7xl items-center gap-1 overflow-x-auto px-4 py-2">
        <Link href="/" className="mr-4 text-lg font-bold tracking-tight">JobOS</Link>
        {LINKS.map(([href, label]) => (
          <Link key={href} href={href} className="whitespace-nowrap rounded-md px-3 py-1.5 text-sm hover:bg-slate-100 dark:hover:bg-slate-800">
            {label}
            {href === "/inbox" && openInterventions > 0 && (
              <span className="ml-1 rounded-full bg-orange-500 px-1.5 text-xs text-white">{openInterventions}</span>
            )}
          </Link>
        ))}
      </div>
    </nav>
  );
}
