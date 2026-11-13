"use client";

import { Loader2, Trash2 } from "lucide-react";
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

/** Delete with a confirmation dialog. The action redirects on success or returns an error. */
export function DeleteButton({
  action,
  title,
  description,
}: {
  action: () => Promise<{ error?: string }>;
  title: string;
  description: string;
}) {
  const [state, run, pending] = useActionState<{ error?: string }>(action, {});

  return (
    <div className="grid justify-items-start gap-2">
      <AlertDialog>
        <AlertDialogTrigger render={<Button variant="destructive" />}>
          <Trash2 />
          Delete
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{title}</AlertDialogTitle>
            <AlertDialogDescription>{description}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <form action={run}>
              <Button type="submit" variant="destructive" disabled={pending}>
                {pending && <Loader2 className="animate-spin" />}
                Delete
              </Button>
            </form>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      {state.error && <p className="text-sm text-destructive">{state.error}</p>}
    </div>
  );
}
