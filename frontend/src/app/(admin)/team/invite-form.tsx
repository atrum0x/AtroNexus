"use client";

import { AlertCircle, CheckCircle2, Loader2, Send } from "lucide-react";
import { useActionState, useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ROLE_DESCRIPTIONS, ROLE_LABELS } from "@/lib/roles";

import { inviteMember, type InviteState } from "./actions";

export function InviteForm({ roles }: { roles: string[] }) {
  const [state, action, pending] = useActionState<InviteState, FormData>(inviteMember, {});
  const [role, setRole] = useState("member");
  const items = roles.map((r) => ({ value: r, label: ROLE_LABELS[r] }));

  return (
    // key: after a successful invite the form remounts empty, ready for the next one.
    <form key={state.sent} action={action} className="grid gap-4">
      {state.error && (
        <Alert variant="destructive">
          <AlertCircle />
          <AlertDescription>{state.error}</AlertDescription>
        </Alert>
      )}
      {state.sent && (
        <Alert>
          <CheckCircle2 />
          <AlertDescription>{state.sent}</AlertDescription>
        </Alert>
      )}
      <div className="grid gap-2">
        <Label htmlFor="invite-email">Email</Label>
        <Input
          id="invite-email"
          name="email"
          type="email"
          autoComplete="off"
          required
          defaultValue={state.email}
          disabled={pending}
        />
      </div>
      <div className="grid gap-2">
        <Label htmlFor="invite-role">Role</Label>
        <Select name="role" items={items} value={role} onValueChange={(v) => v && setRole(v)} disabled={pending}>
          <SelectTrigger id="invite-role" className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {items.map((item) => (
              <SelectItem key={item.value} value={item.value}>
                {item.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <p className="text-xs text-muted-foreground">{ROLE_DESCRIPTIONS[role]}</p>
      </div>
      <Button type="submit" disabled={pending}>
        {pending ? <Loader2 className="animate-spin" /> : <Send />}
        Send invitation
      </Button>
    </form>
  );
}
