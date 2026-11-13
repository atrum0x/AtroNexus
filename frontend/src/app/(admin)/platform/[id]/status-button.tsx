"use client";

import { Loader2 } from "lucide-react";
import { useActionState, useState } from "react";

import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import { changeStatus, type StatusState } from "../actions";

/** Suspends (with an optional reason) or reactivates an organization, after confirming. */
export function StatusButton({ orgId, name, suspended }: { orgId: number; name: string; suspended: boolean }) {
  const [open, setOpen] = useState(false);
  const [state, action, pending] = useActionState<StatusState, FormData>(async (prev, form) => {
    const result = await changeStatus(orgId, prev, form);
    if (!result.error) setOpen(false);
    return result;
  }, {});
  const label = suspended ? "Reactivate" : "Suspend";

  return (
    <div className="grid justify-items-end gap-1">
      <AlertDialog open={open} onOpenChange={setOpen}>
        <AlertDialogTrigger render={<Button variant={suspended ? "default" : "destructive"} />}>
          {label}
        </AlertDialogTrigger>
        <AlertDialogContent>
          <form action={action} className="grid gap-4">
            <input type="hidden" name="status" value={suspended ? "active" : "suspended"} />
            <AlertDialogHeader>
              <AlertDialogTitle>
                {label} {name}?
              </AlertDialogTitle>
              <AlertDialogDescription>
                {suspended
                  ? "Its people can sign in again and its links start working. Nothing was deleted while it was suspended."
                  : "Nobody in it can sign in, everyone signed in is signed out, and its links (such as capture links) stop working. Nothing is deleted; you can reactivate it."}
              </AlertDialogDescription>
            </AlertDialogHeader>
            {!suspended && (
              <div className="grid gap-2">
                <Label htmlFor="reason">Reason (optional, only you see it)</Label>
                <Input id="reason" name="reason" maxLength={500} placeholder="For example: unpaid invoice" />
              </div>
            )}
            {state.error && <p className="text-sm text-destructive">{state.error}</p>}
            <AlertDialogFooter>
              <AlertDialogCancel type="button">Cancel</AlertDialogCancel>
              <Button type="submit" variant={suspended ? "default" : "destructive"} disabled={pending}>
                {pending && <Loader2 className="animate-spin" />}
                {label}
              </Button>
            </AlertDialogFooter>
          </form>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
