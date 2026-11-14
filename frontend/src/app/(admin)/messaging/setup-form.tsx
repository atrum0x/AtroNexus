"use client";

import { AlertCircle, CheckCircle2, Loader2 } from "lucide-react";
import { useActionState, useState } from "react";

import type { MessagingSetupOut } from "@/api/generated/models";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";

import { saveMessagingSetup, type SetupState } from "./actions";

export function MessagingSetupForm({ setup, readOnly }: { setup: MessagingSetupOut; readOnly: boolean }) {
  const [state, action, pending] = useActionState<SetupState, FormData>(saveMessagingSetup, {});
  const [enabled, setEnabled] = useState(setup.enabled);
  const locked = pending || readOnly;

  return (
    <form action={action} className="grid gap-5">
      {state.error && (
        <Alert variant="destructive">
          <AlertCircle />
          <AlertDescription>{state.error}</AlertDescription>
        </Alert>
      )}
      {state.saved && (
        <Alert>
          <CheckCircle2 />
          <AlertDescription>Saved.</AlertDescription>
        </Alert>
      )}
      <div className="grid gap-2">
        <Label htmlFor="default_country_code">Default country code</Label>
        <div className="flex items-center gap-1.5">
          <span className="text-sm text-muted-foreground">+</span>
          <Input
            id="default_country_code"
            name="default_country_code"
            inputMode="numeric"
            pattern="\+?[1-9][0-9]{0,3}"
            placeholder="94"
            defaultValue={setup.default_country_code ?? ""}
            disabled={locked}
            className="w-24"
          />
        </div>
        <p className="text-xs text-muted-foreground">
          For local numbers from IFS: with 94, 0771234567 is sent to +94 77 123 4567. Leave empty if IFS always has the
          country code.
        </p>
      </div>
      <label className="flex items-center gap-3 text-sm">
        <Switch name="enabled" checked={enabled} onCheckedChange={setEnabled} disabled={locked} />
        <span>
          <span className="font-medium">Send messages from IFS.</span>{" "}
          <span className="text-muted-foreground">While off, AtroNexus refuses what IFS sends.</span>
        </span>
      </label>
      {!readOnly && (
        <div>
          <Button type="submit" disabled={pending}>
            {pending && <Loader2 className="animate-spin" />}
            Save
          </Button>
        </div>
      )}
    </form>
  );
}
