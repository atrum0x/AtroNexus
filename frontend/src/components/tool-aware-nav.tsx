import { AdminNav } from "@/components/admin-nav";
import { getCurrentUser } from "@/lib/auth";
import { getTools } from "@/lib/tools";

/**
 * The admin menu: links for the tools this organization has switched on, and
 * Platform for the platform admin. Render inside <Suspense>.
 */
export async function ToolAwareNav() {
  const [tools, user] = await Promise.all([getTools(), getCurrentUser()]);
  const enabled = tools.filter((t) => t.enabled).map((t) => t.code);
  return <AdminNav enabledTools={enabled} platformAdmin={user.is_platform_admin} />;
}
