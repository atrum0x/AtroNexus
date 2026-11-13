import { Suspense } from "react";

import { AppBreadcrumb } from "@/components/app-header";
import { AppSidebar } from "@/components/app-sidebar";
import { AppSidebarLoader } from "@/components/app-sidebar-loader";
import { Separator } from "@/components/ui/separator";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { TooltipProvider } from "@/components/ui/tooltip";
import { VerifyEmailBanner } from "@/components/verify-email-banner";

// The signed-in app: a collapsible sidebar (Ctrl/Cmd+B), a slim header with
// the breadcrumb, and the page. The layout stays mounted between pages, so
// the sidebar keeps its open/collapsed state while you move around.
export default function AdminLayout({ children }: LayoutProps<"/">) {
  return (
    <TooltipProvider>
      <SidebarProvider>
        <Suspense fallback={<AppSidebar />}>
          <AppSidebarLoader />
        </Suspense>
        <SidebarInset>
          <header className="sticky top-0 z-10 flex h-14 shrink-0 items-center gap-2 border-b bg-background/95 px-4 backdrop-blur supports-backdrop-filter:bg-background/80">
            <SidebarTrigger className="-ml-1" />
            <Separator orientation="vertical" className="mr-2 data-vertical:h-4 data-vertical:self-center" />
            <Suspense>
              <AppBreadcrumb />
            </Suspense>
          </header>
          <Suspense>
            <VerifyEmailBanner />
          </Suspense>
          <div className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 md:px-8 md:py-8">{children}</div>
        </SidebarInset>
      </SidebarProvider>
    </TooltipProvider>
  );
}
