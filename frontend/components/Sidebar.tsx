"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

const NAV_ITEMS = [
  { href: "/queue", label: "Queue" },
  { href: "/metrics", label: "Metrics" },
  { href: "/rules", label: "Rules" },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const router = useRouter();

  function handleLogout() {
    logout();
    router.replace("/login");
  }

  return (
    <aside className="flex h-screen w-56 shrink-0 flex-col border-r border-hairline bg-panel">
      <div className="flex items-center gap-2 border-b border-hairline px-5 py-4">
        <span className="h-2 w-2 rounded-full bg-accent" />
        <span className="font-display text-sm font-semibold tracking-tight text-text-primary">
          TrustGuard
        </span>
      </div>

      <nav className="flex-1 px-3 py-4">
        {NAV_ITEMS.map((item) => {
          const active = pathname?.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`mb-1 flex items-center rounded-md px-3 py-2 text-sm transition ${
                active
                  ? "bg-panel-raised text-text-primary"
                  : "text-text-muted hover:bg-panel-raised hover:text-text-primary"
              }`}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-hairline px-5 py-4">
        <p className="truncate font-mono text-xs text-text-muted">{user?.email}</p>
        <p className="mb-3 font-mono text-[11px] uppercase tracking-wide text-text-faint">{user?.role}</p>
        <button
          onClick={handleLogout}
          className="font-mono text-xs text-text-faint transition hover:text-text-primary"
        >
          Sign out
        </button>
      </div>
    </aside>
  );
}
