"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/", label: "Home", exact: true },
  { href: "/capture", label: "Capture pages", exact: false },
  { href: "/connections", label: "IFS connections", exact: false },
  { href: "/team", label: "Team", exact: false },
];

/** Reads the URL, so render it inside <Suspense> with <NavLinks /> as the fallback. */
export function AdminNav() {
  return <NavLinks pathname={usePathname()} />;
}

export function NavLinks({ pathname }: { pathname?: string }) {
  return (
    <nav className="flex items-center gap-1 text-sm">
      {LINKS.map((link) => {
        const active =
          pathname !== undefined &&
          (link.exact ? pathname === link.href : pathname.startsWith(link.href));
        return (
          <Link
            key={link.href}
            href={link.href}
            className={cn(
              "rounded-md px-2.5 py-1.5 text-muted-foreground transition-colors hover:text-foreground",
              active && "bg-muted text-foreground",
            )}
          >
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}
