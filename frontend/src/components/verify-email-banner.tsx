import { getCurrentUser } from "@/lib/auth";

import { ResendVerificationButton } from "./resend-verification-button";

/** Shown until the signed-in user confirms their email. Render inside <Suspense>. */
export async function VerifyEmailBanner() {
  const user = await getCurrentUser();
  if (user.email_verified) return null;

  return (
    <div className="border-b bg-amber-50 text-amber-950 dark:bg-amber-950/40 dark:text-amber-100">
      <div className="mx-auto flex w-full max-w-5xl flex-wrap items-center gap-x-4 gap-y-2 px-6 py-2.5 text-sm">
        <p className="flex-1">
          Confirm your email address to connect AtroNexus to IFS. We sent a link to{" "}
          <strong className="font-medium">{user.email}</strong>.
        </p>
        <ResendVerificationButton />
      </div>
    </div>
  );
}
