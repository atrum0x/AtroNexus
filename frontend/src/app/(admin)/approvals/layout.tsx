import { Suspense } from "react";

import { TableSkeleton } from "@/components/page-header";
import { ToolGate } from "@/components/tool-gate";
import { APPROVALS } from "@/lib/tools";

// Every approvals admin page needs the tool switched on; the API refuses otherwise.
export default function ApprovalsLayout({ children }: LayoutProps<"/approvals">) {
  return (
    <Suspense fallback={<TableSkeleton />}>
      <ToolGate code={APPROVALS} name="Approve from email">
        {children}
      </ToolGate>
    </Suspense>
  );
}
