import Link from "next/link";
import { Suspense } from "react";

import { AdminNav, NavLinks } from "@/components/admin-nav";
import { Button } from "@/components/ui/button";

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
            <AdminNav />
          </Suspense>
          <form action={logout} className="ml-auto">
            <Button type="submit" variant="outline" size="sm">
              Sign out
            </Button>
          </form>
        </div>
      </header>
      <main className="mx-auto w-full max-w-5xl flex-1 px-6 py-8">{children}</main>
    </div>
  );
}
