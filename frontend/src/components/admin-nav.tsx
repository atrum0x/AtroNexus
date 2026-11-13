"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

// `tool`: shown only while the organization has that tool switched on.
// `platform`: shown only to the platform admin.
const LINKS: { href: string; label: string; exact: boolean; tool?: string; platform?: boolean }[] = [
  { href: "/", label: "Home", exact: true },
  { href: "/capture", label: "Capture pages", exact: false, tool: "capture" },
  { href: "/connections", label: "IFS connections", exact: false },
  { href: "/team", label: "Team", exact: false },
  { href: "/tools", label: "Tools", exact: false },
  { href: "/platform", label: "Platform", exact: false, platform: true },
];

/**
 * Reads the URL, so render it inside <Suspense> with <NavLinks /> as the
 * fallback. `enabledTools` comes from the server (see ToolAwareNav).
 */
export function AdminNav({ enabledTools, platformAdmin }: { enabledTools: string[]; platformAdmin: boolean }) {
  return <NavLinks pathname={usePathname()} enabledTools={enabledTools} platformAdmin={platformAdmin} />;
}

export function NavLinks({
  pathname,
  enabledTools = [],
  platformAdmin = false,
}: {
  pathname?: string;
  enabledTools?: string[];
  platformAdmin?: boolean;
}) {
  return (
    <nav className="flex items-center gap-1 overflow-x-auto text-sm">
      {LINKS.filter(
        (link) => (!link.tool || enabledTools.includes(link.tool)) && (!link.platform || platformAdmin),
      ).map((link) => {
        const active =
          pathname !== undefined &&
          (link.exact ? pathname === link.href : pathname.startsWith(link.href));
        return (
          <Link
            key={link.href}
            href={link.href}
            className={cn(
              "shrink-0 rounded-md px-2.5 py-1.5 text-muted-foreground transition-colors hover:text-foreground",
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
