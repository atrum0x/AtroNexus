import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { AuthShell, authLinkClass } from "@/components/auth-shell";

import { ResetPasswordForm } from "./reset-password-form";

export const metadata: Metadata = {
  title: "Choose a new password · AtroNexus",
  robots: { index: false, follow: false },
};

export default function ResetPasswordPage({ searchParams }: PageProps<"/reset-password">) {
  return (
    <AuthShell
      title="Choose a new password"
      description="You'll be signed out everywhere else."
      footer={
        <Link href="/login" className={authLinkClass}>
          Back to sign in
        </Link>
      }
    >
      <Suspense fallback={<div className="h-48 animate-pulse rounded-lg bg-muted" />}>
        <WithToken searchParams={searchParams} />
      </Suspense>
    </AuthShell>
  );
}

async function WithToken({ searchParams }: { searchParams: PageProps<"/reset-password">["searchParams"] }) {
  const { token } = await searchParams;
  return <ResetPasswordForm token={typeof token === "string" ? token : ""} />;
}
