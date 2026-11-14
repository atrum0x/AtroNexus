import { Suspense } from "react";

import { TableSkeleton } from "@/components/page-header";
import { ToolGate } from "@/components/tool-gate";
import { MESSAGING } from "@/lib/tools";

import { MessagingNav } from "./messaging-nav";

// Every messaging admin page needs the tool switched on; the API refuses otherwise.
export default function MessagingLayout({ children }: LayoutProps<"/messaging">) {
  return (
    <Suspense fallback={<TableSkeleton />}>
      <ToolGate code={MESSAGING} name="Messaging hub">
        <div className="grid gap-6">
          <MessagingNav />
          {children}
        </div>
      </ToolGate>
    </Suspense>
  );
}
