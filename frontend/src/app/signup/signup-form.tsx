"use client";

import { AlertCircle, Loader2 } from "lucide-react";
import { useActionState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { signup, type SignupState } from "@/lib/account-actions";

export function SignupForm() {
  const [state, action, pending] = useActionState<SignupState, FormData>(signup, {});
  const v = state.values ?? {};

  return (
    <form action={action} className="grid gap-4">
      {state.error && (
        <Alert variant="destructive">
          <AlertCircle />
          <AlertDescription>{state.error}</AlertDescription>
        </Alert>
      )}

      <div className="grid gap-2">
        <Label htmlFor="organization_name">Company name</Label>
        <Input
          id="organization_name"
          name="organization_name"
          autoComplete="organization"
          maxLength={100}
          autoFocus
          required
          defaultValue={v.organization_name}
          disabled={pending}
        />
      </div>

      <div className="grid gap-2">
        <Label htmlFor="name">Your name</Label>
        <Input
          id="name"
          name="name"
          autoComplete="name"
          maxLength={100}
          required
          defaultValue={v.name}
          disabled={pending}
        />
      </div>

      <div className="grid gap-2">
        <Label htmlFor="email">Work email</Label>
        <Input
          id="email"
          name="email"
          type="email"
          autoComplete="email"
          maxLength={254}
          required
          defaultValue={v.email}
          disabled={pending}
        />
      </div>

      <div className="grid gap-2">
        <Label htmlFor="password">Password</Label>
        <Input
          id="password"
          name="password"
          type="password"
          autoComplete="new-password"
          minLength={8}
          maxLength={256}
          required
          aria-describedby="password-hint"
          disabled={pending}
        />
        <p id="password-hint" className="text-xs text-muted-foreground">
          At least 8 characters.
        </p>
      </div>

      <Button type="submit" size="lg" className="w-full" disabled={pending}>
        {pending && <Loader2 className="animate-spin" />}
        {pending ? "Creating your account…" : "Create account"}
      </Button>
    </form>
  );
}
