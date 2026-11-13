"use client";

import { AlertCircle, CheckCircle2, Loader2 } from "lucide-react";
import Link from "next/link";
import { useActionState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { resetPassword, type ResetPasswordState } from "@/lib/account-actions";

export function ResetPasswordForm({ token }: { token: string }) {
  const [state, action, pending] = useActionState<ResetPasswordState, FormData>(resetPassword, {});

  if (!token) {
    return (
      <Alert variant="destructive">
        <AlertCircle />
        <AlertDescription>
          This link is incomplete. Open the link from the email again, or{" "}
          <Link href="/forgot-password" className="underline underline-offset-4">
            ask for a new one
          </Link>
          .
        </AlertDescription>
      </Alert>
    );
  }

  if (state.done) {
    return (
      <div className="grid gap-4">
        <Alert>
          <CheckCircle2 />
          <AlertDescription>Your password is changed.</AlertDescription>
        </Alert>
        <Button size="lg" className="w-full" render={<Link href="/login" />} nativeButton={false}>
          Sign in
        </Button>
      </div>
    );
  }

  return (
    <form action={action} className="grid gap-4">
      {state.error && (
        <Alert variant="destructive">
          <AlertCircle />
          <AlertDescription>{state.error}</AlertDescription>
        </Alert>
      )}
      <input type="hidden" name="token" value={token} />
      <div className="grid gap-2">
        <Label htmlFor="password">New password</Label>
        <Input
          id="password"
          name="password"
          type="password"
          autoComplete="new-password"
          minLength={8}
          maxLength={256}
          autoFocus
          required
          disabled={pending}
        />
      </div>
      <div className="grid gap-2">
        <Label htmlFor="confirm">Repeat new password</Label>
        <Input
          id="confirm"
          name="confirm"
          type="password"
          autoComplete="new-password"
          minLength={8}
          maxLength={256}
          required
          disabled={pending}
        />
      </div>
      <Button type="submit" size="lg" className="w-full" disabled={pending}>
        {pending && <Loader2 className="animate-spin" />}
        {pending ? "Saving…" : "Change password"}
      </Button>
    </form>
  );
}
