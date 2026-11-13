import { Link2Off } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { ApiError } from "@/api/fetcher";
import { getInvitation } from "@/api/generated/endpoints/team-public/team-public";
import { AuthShell, authLinkClass } from "@/components/auth-shell";
import { ROLE_LABELS } from "@/lib/roles";

import { AcceptForm } from "./accept-form";

export const metadata: Metadata = {
  title: "Join your team · AtroNexus",
  robots: { index: false, follow: false },
};

export default function InvitePage({ searchParams }: PageProps<"/invite">) {
  return (
    <Suspense
      fallback={
        <AuthShell title="Join your team">
          <div className="h-48 animate-pulse rounded-lg bg-muted" />
        </AuthShell>
      }
    >
      <Invite searchParams={searchParams} />
    </Suspense>
  );
}

async function Invite({ searchParams }: { searchParams: PageProps<"/invite">["searchParams"] }) {
  const { token } = await searchParams;

  let invitation;
  if (typeof token === "string" && token) {
    try {
      invitation = await getInvitation(token);
    } catch (err) {
      if (!(err instanceof ApiError && (err.status === 404 || err.status === 422))) throw err;
    }
  }

  if (!invitation || typeof token !== "string") {
    return (
      <AuthShell
        title="Invitation not valid"
        footer={
          <Link href="/login" className={authLinkClass}>
            Go to sign in
          </Link>
        }
      >
        <div className="flex flex-col items-center gap-3 py-2 text-center">
          <Link2Off className="size-8 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">
            This invitation was already used, was cancelled, or has expired. Ask the person who invited you
            to send a new one.
          </p>
        </div>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title={`Join ${invitation.organization_name}`}
      description={
        <>
          {invitation.invited_by ?? "Someone"} invited you as{" "}
          <strong className="font-medium text-foreground">{ROLE_LABELS[invitation.role].toLowerCase()}</strong>.
          Choose your name and a password to finish.
        </>
      }
    >
      <AcceptForm token={token} email={invitation.email} />
    </AuthShell>
  );
}
