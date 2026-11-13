import { AppSidebar } from "@/components/app-sidebar";
import { getCurrentUser } from "@/lib/auth";
import { getTools } from "@/lib/tools";

/** Loads what the sidebar shows. Render inside <Suspense fallback={<AppSidebar />}>. */
export async function AppSidebarLoader() {
  const [user, tools] = await Promise.all([getCurrentUser(), getTools()]);
  return (
    <AppSidebar
      data={{
        organization: user.organization.name,
        role: user.role,
        user: { name: user.name ?? user.username ?? user.email ?? "You", email: user.email },
        enabledTools: tools.filter((t) => t.enabled).map((t) => t.code),
        platformAdmin: user.is_platform_admin,
      }}
    />
  );
}
