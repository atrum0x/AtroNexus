import { Suspense } from "react";

import { TableSkeleton } from "@/components/page-header";
import { ToolGate } from "@/components/tool-gate";
import { CAPTURE } from "@/lib/tools";

// Every capture admin page needs the tool switched on; the API refuses otherwise.
export default function CaptureLayout({ children }: LayoutProps<"/capture">) {
  return (
    <Suspense fallback={<TableSkeleton />}>
      <ToolGate code={CAPTURE} name="The capture page">
        {children}
      </ToolGate>
    </Suspense>
  );
}
