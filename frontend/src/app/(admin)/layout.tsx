import Link from "next/link";
import { Suspense } from "react";

import { NavLinks } from "@/components/admin-nav";
import { ToolAwareNav } from "@/components/tool-aware-nav";
import { Button } from "@/components/ui/button";
import { VerifyEmailBanner } from "@/components/verify-email-banner";

import { logout } from "../login/actions";

export default function AdminLayout({ children }: LayoutProps<"/">) {
  return (
    <div className="flex flex-1 flex-col">
      <header className="border-b">
        <div className="mx-auto flex h-14 w-full max-w-5xl items-center gap-6 px-6">
          <Link href="/" className="font-semibold tracking-tight">
            AtroNexus
          </Link>
          <Suspense fallback={<NavLinks />}>
            <ToolAwareNav />
          </Suspense>
          <form action={logout} className="ml-auto">
            <Button type="submit" variant="outline" size="sm">
              Sign out
            </Button>
          </form>
        </div>
      </header>
      <Suspense>
        <VerifyEmailBanner />
      </Suspense>
      <main className="mx-auto w-full max-w-5xl flex-1 px-6 py-8">{children}</main>
    </div>
  );
}
