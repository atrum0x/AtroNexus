import { AdminNav } from "@/components/admin-nav";
import { getTools } from "@/lib/tools";

/** The admin menu, with links for the tools this organization has switched on. Render inside <Suspense>. */
export async function ToolAwareNav() {
  const enabled = (await getTools()).filter((t) => t.enabled).map((t) => t.code);
  return <AdminNav enabledTools={enabled} />;
}
