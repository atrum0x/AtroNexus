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

/** A small destructive action in a table row, confirmed in a dialog first. */
export function ConfirmButton({
  action,
  label,
  title,
  description,
  tone = "destructive",
}: {
  action: () => Promise<{ error?: string }>;
  label: string;
  title: string;
  description: string;
  /** "neutral" for actions that change something but delete nothing. */
  tone?: "destructive" | "neutral";
}) {
  // Controlled, so the dialog closes once the action succeeds (when the
  // button stays on the page, nothing else would close it).
  const [open, setOpen] = useState(false);
  const [state, run, pending] = useActionState<{ error?: string }>(async () => {
    const result = await action();
    if (!result.error) setOpen(false);
    return result;
  }, {});

  return (
    <div className="grid justify-items-end gap-1">
      <AlertDialog open={open} onOpenChange={setOpen}>
        <AlertDialogTrigger
          render={
            tone === "destructive" ? (
              <Button variant="ghost" size="sm" className="text-destructive" />
            ) : (
              <Button variant="outline" size="sm" />
            )
          }
        >
          {label}
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{title}</AlertDialogTitle>
            <AlertDialogDescription>{description}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep</AlertDialogCancel>
            <form action={run}>
              <Button
                type="submit"
                variant={tone === "destructive" ? "destructive" : "default"}
                disabled={pending}
              >
                {pending && <Loader2 className="animate-spin" />}
                {label}
              </Button>
            </form>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      {state.error && <p className="text-xs text-destructive">{state.error}</p>}
    </div>
  );
}
