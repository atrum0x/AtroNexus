import { CheckCircle2, MailWarning } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { ApiError } from "@/api/fetcher";
import { verifyEmail } from "@/api/generated/endpoints/auth/auth";
import { AuthShell } from "@/components/auth-shell";
import { Button } from "@/components/ui/button";

export const metadata: Metadata = {
  title: "Confirm your email · AtroNexus",
  robots: { index: false, follow: false },
};

export default function VerifyEmailPage({ searchParams }: PageProps<"/verify-email">) {
  return (
    <AuthShell title="Confirm your email">
      <Suspense fallback={<div className="h-24 animate-pulse rounded-lg bg-muted" />}>
        <Result searchParams={searchParams} />
      </Suspense>
    </AuthShell>
  );
}

// Opening the link confirms the address; there's nothing else to do here.
async function Result({ searchParams }: { searchParams: PageProps<"/verify-email">["searchParams"] }) {
  const { token } = await searchParams;

  let error: string | undefined;
  if (typeof token !== "string" || !token) {
    error = "This link is incomplete. Open the link from the email again.";
  } else {
    try {
      await verifyEmail({ token });
    } catch (err) {
      if (!(err instanceof ApiError)) throw err;
      error =
        err.status === 400
          ? "This link has expired or was already used. Sign in and ask for a new one from the banner at the top."
          : err.message;
    }
  }

  return (
    <div className="flex flex-col items-center gap-4 py-2 text-center">
      {error ? (
        <MailWarning className="size-8 text-muted-foreground" />
      ) : (
        <CheckCircle2 className="size-8 text-emerald-600" />
      )}
      <p className="text-sm text-muted-foreground">
        {error ?? "Your email address is confirmed. You can now connect AtroNexus to IFS."}
      </p>
      <Button size="lg" className="w-full" render={<Link href="/" />} nativeButton={false}>
        Continue to AtroNexus
      </Button>
    </div>
  );
}
