"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

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
  connections: "IFS connections",
  team: "Team",
  tools: "Tools",
  platform: "Customers",
};

const PAGES: Record<string, string> = { new: "New", log: "Log" };

/**
 * Where you are: the section, and the page inside it ("New", or "Details" for
 * a record). Reads the URL, so render it inside <Suspense>.
 */
export function AppBreadcrumb() {
  const [section = "", page] = usePathname().split("/").filter(Boolean);
  const label = SECTIONS[section] ?? section;

  return (
    <Breadcrumb>
      <BreadcrumbList>
        {page ? (
          <>
            <BreadcrumbItem className="hidden md:block">
              <BreadcrumbLink render={<Link href={`/${section}`} />}>{label}</BreadcrumbLink>
            </BreadcrumbItem>
            <BreadcrumbSeparator className="hidden md:block" />
            <BreadcrumbItem>
              <BreadcrumbPage>{PAGES[page] ?? "Details"}</BreadcrumbPage>
            </BreadcrumbItem>
          </>
        ) : (
          <BreadcrumbItem>
            <BreadcrumbPage>{label}</BreadcrumbPage>
          </BreadcrumbItem>
        )}
      </BreadcrumbList>
    </Breadcrumb>
  );
}
