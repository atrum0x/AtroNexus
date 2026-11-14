"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

const TABS = [
  { href: "/messaging", label: "Overview", exact: true },
  { href: "/messaging/templates", label: "Templates" },
  { href: "/messaging/scenarios", label: "Scenarios" },
];

/** Tabs between the messaging pages. Reads the URL, so it sits inside <Suspense> (the layout's). */
export function MessagingNav() {
  const pathname = usePathname();
  return (
    <nav className="flex gap-1 overflow-x-auto overflow-y-hidden border-b [scrollbar-width:none]" aria-label="Messaging">
      {TABS.map((tab) => {
        const active = tab.exact ? pathname === tab.href : pathname.startsWith(tab.href);
        return (
          <Link
            key={tab.href}
            href={tab.href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "-mb-px border-b-2 px-3 py-2 text-sm font-medium whitespace-nowrap transition-colors",
              active
                ? "border-primary text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            {tab.label}
          </Link>
        );
      })}
    </nav>
  );
}
