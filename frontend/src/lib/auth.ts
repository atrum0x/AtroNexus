import "server-only";

import { redirect } from "next/navigation";
import { cache } from "react";

import { getMe } from "@/api/generated/endpoints/auth/auth";
import type { UserOut } from "@/api/generated/models";
import { getSessionToken } from "@/lib/session";

/**
 * Returns the signed-in user, or redirects to /login. Call it inside a <Suspense> boundary.
 * An expired token is handled by the API mutator, which redirects to /session-expired.
 */
export const getCurrentUser = cache(async (): Promise<UserOut> => {
  if (!(await getSessionToken())) redirect("/login");
  return getMe();
});
