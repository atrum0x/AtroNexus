"use client";

import { Loader2 } from "lucide-react";
import { useActionState } from "react";

import { Button } from "@/components/ui/button";
import { resendVerification, type ResendState } from "@/lib/account-actions";

export function ResendVerificationButton() {
  const [state, action, pending] = useActionState<ResendState>(resendVerification, {});

  if (state.sent) return <span className="text-sm">{state.sent}</span>;

  return (
    <form action={action} className="flex items-center gap-2">
      {state.error && <span className="text-sm text-destructive">{state.error}</span>}
      <Button type="submit" variant="outline" size="sm" disabled={pending} className="bg-transparent">
        {pending && <Loader2 className="animate-spin" />}
        Send the link again
      </Button>
    </form>
  );
}
