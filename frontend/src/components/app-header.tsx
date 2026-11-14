"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Fragment } from "react";

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";

const SECTIONS: Record<string, string> = {
  "": "Dashboard",
  capture: "Capture pages",
  approvals: "Approvals",
  messaging: "Messaging",
  connections: "IFS connections",
  team: "Team",
  tools: "Tools",
  platform: "Customers",
};

const PAGES: Record<string, string> = { new: "New", log: "Log", templates: "Templates", scenarios: "Scenarios" };

/**
 * Where you are: the section, then each page inside it ("Templates", "New",
 * or "Details" for a record). Reads the URL, so render it inside <Suspense>.
 */
export function AppBreadcrumb() {
  const segments = usePathname().split("/").filter(Boolean);
  const crumbs = (segments.length ? segments : [""]).map((segment, i) => ({
    href: "/" + segments.slice(0, i + 1).join("/"),
    label: i === 0 ? (SECTIONS[segment] ?? segment) : (PAGES[segment] ?? "Details"),
  }));

  return (
    <Breadcrumb>
      <BreadcrumbList>
        {crumbs.map((crumb, i) =>
          i < crumbs.length - 1 ? (
            <Fragment key={crumb.href}>
              <BreadcrumbItem className="hidden md:block">
                <BreadcrumbLink render={<Link href={crumb.href} />}>{crumb.label}</BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator className="hidden md:block" />
            </Fragment>
          ) : (
            <BreadcrumbItem key={crumb.href}>
              <BreadcrumbPage>{crumb.label}</BreadcrumbPage>
            </BreadcrumbItem>
          ),
        )}
      </BreadcrumbList>
    </Breadcrumb>
  );
}
