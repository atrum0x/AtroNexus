"use client";

import { AlertCircle, Loader2, MailCheck } from "lucide-react";
import { useActionState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { forgotPassword, type ForgotPasswordState } from "@/lib/account-actions";

export function ForgotPasswordForm() {
  const [state, action, pending] = useActionState<ForgotPasswordState, FormData>(forgotPassword, {});

  if (state.sent) {
    return (
      <Alert>
        <MailCheck />
        <AlertDescription>
          {state.sent} The link works for 1 hour. Check your spam folder if it doesn&apos;t arrive.
        </AlertDescription>
      </Alert>
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
      <div className="grid gap-2">
        <Label htmlFor="email">Email</Label>
        <Input
          id="email"
          name="email"
          type="email"
          autoComplete="email"
          autoFocus
          required
          defaultValue={state.email}
          disabled={pending}
        />
      </div>
      <Button type="submit" size="lg" className="w-full" disabled={pending}>
        {pending && <Loader2 className="animate-spin" />}
        {pending ? "Sending…" : "Send reset link"}
      </Button>
    </form>
  );
}
