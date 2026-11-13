import "server-only";

import { unstable_rethrow } from "next/navigation";

import { ApiError } from "@/api/fetcher";

/**
 * Turns an error from the API into a sentence a user can act on.
 *
 * Call it first thing in a catch block. It rethrows Next's own control-flow
 * errors (redirect, notFound), such as the mutator's redirect to
 * /session-expired, so a catch-all doesn't swallow them.
 */
export function errorMessage(err: unknown): string {
  unstable_rethrow(err);
  if (err instanceof ApiError) return err.message;
  return "Can't reach the server. Try again in a moment.";
}

/** Reads a trimmed string field from a form, or undefined when empty. */
export function field(form: FormData, name: string): string | undefined {
  const value = form.get(name);
  if (typeof value !== "string") return undefined;
  const trimmed = value.trim();
  return trimmed === "" ? undefined : trimmed;
}
