"use client";

import { Loader2 } from "lucide-react";
import { useActionState } from "react";

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
}: {
  action: () => Promise<{ error?: string }>;
  label: string;
  title: string;
  description: string;
}) {
  const [state, run, pending] = useActionState<{ error?: string }>(action, {});

  return (
    <div className="grid justify-items-end gap-1">
      <AlertDialog>
        <AlertDialogTrigger render={<Button variant="ghost" size="sm" className="text-destructive" />}>
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
              <Button type="submit" variant="destructive" disabled={pending}>
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
