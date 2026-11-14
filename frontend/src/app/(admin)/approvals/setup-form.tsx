"use client";

import { AlertCircle, CheckCircle2, KeyRound, Loader2 } from "lucide-react";
import { useActionState, useState, useTransition } from "react";

import type { IfsConnectionOut, SetupOut } from "@/api/generated/models";
import { CopyField } from "@/components/copy-field";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";

import { newHookKey, saveSetup, type SetupState } from "./actions";

/** Creates a hook key and shows it once, to paste into the IFS routing address. */
export function HookKey({ hasKey, hint, readOnly }: { hasKey: boolean; hint: string | null; readOnly: boolean }) {
  const [key, setKey] = useState<string>();
  const [error, setError] = useState<string>();
  const [pending, start] = useTransition();

  function create() {
    if (hasKey && !window.confirm("Make a new key? The old one stops working at once, so IFS must get the new one.")) {
      return;
    }
    start(async () => {
      const res = await newHookKey();
      if (res.key) setKey(res.key);
      else setError(res.error);
    });
  }

  return (
    <div className="grid gap-2">
      {key ? (
        <>
          <CopyField value={key} label="hook key" />
          <p className="text-xs text-muted-foreground">
            Copy it now: it isn&apos;t shown again. Paste it into the bearer token of the routing address
            C_ATX_APPROVAL_ADDR in IFS.
          </p>
        </>
      ) : (
        <p className="text-sm text-muted-foreground">
          {hasKey ? `A key ending in …${hint} is set.` : "No key yet."}
        </p>
      )}
      {error && <p className="text-sm text-destructive">{error}</p>}
      {!readOnly && !key && (
        <div>
          <Button type="button" variant="outline" disabled={pending} onClick={create}>
            {pending ? <Loader2 className="animate-spin" /> : <KeyRound />}
            {hasKey ? "Make a new key" : "Create hook key"}
          </Button>
        </div>
      )}
    </div>
  );
}

export function SetupForm({
  setup,
  connections,
  readOnly,
}: {
  setup: SetupOut;
  connections: IfsConnectionOut[];
  readOnly: boolean;
}) {
  const [state, action, pending] = useActionState<SetupState, FormData>(saveSetup, {});
  const items = connections.map((c) => ({ value: String(c.id), label: c.name }));
  const [connection, setConnection] = useState<string | null>(setup.connection_id ? String(setup.connection_id) : null);
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
        <Label htmlFor="connection_id">IFS connection</Label>
        <Select name="connection_id" items={items} value={connection} onValueChange={setConnection} disabled={locked}>
          <SelectTrigger id="connection_id" className="w-full">
            <SelectValue placeholder="Pick a connection" />
          </SelectTrigger>
          <SelectContent>
            {items.map((c) => (
              <SelectItem key={c.value} value={c.value}>
                {c.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <p className="text-xs text-muted-foreground">
          Its service user needs the projection CAtxApprovalHandling and the system privilege IMPERSONATE USER.
        </p>
      </div>
      <div className="grid gap-2">
        <Label htmlFor="link_days">Links work for (days)</Label>
        <Input
          id="link_days"
          name="link_days"
          type="number"
          min={1}
          max={30}
          defaultValue={setup.link_days}
          disabled={locked}
          className="w-28"
        />
      </div>
      <label className="flex items-center gap-3 text-sm">
        <Switch name="enabled" checked={enabled} onCheckedChange={setEnabled} disabled={locked} />
        <span>
          <span className="font-medium">Send approval emails.</span>{" "}
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
