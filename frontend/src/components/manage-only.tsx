import { getCurrentUser } from "@/lib/auth";
import { canManage } from "@/lib/roles";

/**
 * Renders its children only for owners and admins, and `fallback` (default:
 * nothing) for members. Wrap it in <Suspense>.
 */
export async function ManageOnly({
  children,
  fallback = null,
}: {
  children: React.ReactNode;
  fallback?: React.ReactNode;
}) {
  const user = await getCurrentUser();
  return canManage(user) ? children : fallback;
}

export function MembersCantChange({ what }: { what: string }) {
  return <p className="text-sm text-muted-foreground">Only owners and admins can {what}.</p>;
}
