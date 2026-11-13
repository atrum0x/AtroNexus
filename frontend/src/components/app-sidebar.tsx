"use client";

import {
  Blocks,
  Building2,
  ChevronsUpDown,
  LayoutDashboard,
  LogOut,
  MapPin,
  Monitor,
  Moon,
  PlugZap,
  Sun,
  Users,
  type LucideIcon,
} from "lucide-react";
import { useTheme } from "next-themes";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTransition } from "react";

import { logout } from "@/app/login/actions";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  useSidebar,
} from "@/components/ui/sidebar";
import { Skeleton } from "@/components/ui/skeleton";

export type SidebarData = {
  organization: string;
  role: string;
  user: { name: string; email: string | null };
  enabledTools: string[];
  platformAdmin: boolean;
};

type NavItem = { href: string; label: string; icon: LucideIcon; exact?: boolean };

/** The menu, grouped. Tool links appear only while the tool is switched on. */
function sections(data: SidebarData): { label?: string; items: NavItem[] }[] {
  const tools: NavItem[] = [];
  if (data.enabledTools.includes("capture")) {
    tools.push({ href: "/capture", label: "Capture pages", icon: MapPin });
  }
  tools.push({ href: "/tools", label: "All tools", icon: Blocks });

  const result = [
    { items: [{ href: "/", label: "Dashboard", icon: LayoutDashboard, exact: true }] },
    { label: "Tools", items: tools },
    {
      label: "Organization",
      items: [
        { href: "/connections", label: "IFS connections", icon: PlugZap },
        { href: "/team", label: "Team", icon: Users },
      ],
    },
  ];
  if (data.platformAdmin) {
    result.push({ label: "Platform", items: [{ href: "/platform", label: "Customers", icon: Building2 }] });
  }
  return result;
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  const letters = parts.length > 1 ? parts[0][0] + parts[parts.length - 1][0] : (parts[0] ?? "?").slice(0, 2);
  return letters.toUpperCase();
}

const ROLE_LABELS: Record<string, string> = { owner: "Owner", admin: "Admin", member: "Member" };

/**
 * The app's sidebar (shadcn sidebar-07: collapses to icons, a drawer on phones).
 * Without data it shows placeholders while the server loads them.
 */
export function AppSidebar({ data }: { data?: SidebarData }) {
  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <OrganizationBlock data={data} />
      </SidebarHeader>
      <SidebarContent>{data ? <Nav data={data} /> : <NavSkeleton />}</SidebarContent>
      <SidebarFooter>{data && <UserMenu data={data} />}</SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}

function OrganizationBlock({ data }: { data?: SidebarData }) {
  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <SidebarMenuButton size="lg" render={<Link href="/" />} tooltip={data?.organization ?? "AtroNexus"}>
          <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-sidebar-primary text-sm font-semibold text-sidebar-primary-foreground">
            A
          </div>
          <div className="grid flex-1 text-left text-sm leading-tight">
            <span className="truncate font-semibold">AtroNexus</span>
            <span className="truncate text-xs text-sidebar-foreground/70">{data?.organization ?? " "}</span>
          </div>
        </SidebarMenuButton>
      </SidebarMenuItem>
    </SidebarMenu>
  );
}

function Nav({ data }: { data: SidebarData }) {
  const pathname = usePathname();
  const { isMobile, setOpenMobile } = useSidebar();

  return sections(data).map((section, i) => (
    <SidebarGroup key={section.label ?? i}>
      {section.label && <SidebarGroupLabel>{section.label}</SidebarGroupLabel>}
      <SidebarMenu>
        {section.items.map((item) => {
          const active = item.exact ? pathname === item.href : pathname.startsWith(item.href);
          return (
            <SidebarMenuItem key={item.href}>
              <SidebarMenuButton
                isActive={active}
                tooltip={item.label}
                render={<Link href={item.href} />}
                // On phones the sidebar is a drawer: close it after choosing.
                onClick={() => isMobile && setOpenMobile(false)}
              >
                <item.icon />
                <span>{item.label}</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          );
        })}
      </SidebarMenu>
    </SidebarGroup>
  ));
}

// Placeholder rows while the menu loads. Fixed widths: shadcn's
// SidebarMenuSkeleton picks a random one, which prerendering doesn't allow.
const SKELETON_WIDTHS = ["70%", "55%", "80%", "60%", "65%"];

function NavSkeleton() {
  return (
    <SidebarGroup>
      <SidebarMenu>
        {SKELETON_WIDTHS.map((width) => (
          <SidebarMenuItem key={width} className="flex h-8 items-center gap-2 rounded-md px-2">
            <Skeleton className="size-4 rounded-md" />
            <Skeleton className="h-4 flex-1 group-data-[collapsible=icon]:hidden" style={{ maxWidth: width }} />
          </SidebarMenuItem>
        ))}
      </SidebarMenu>
    </SidebarGroup>
  );
}

const THEMES = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "Same as device", icon: Monitor },
];

function ThemeChoice() {
  const { theme, setTheme } = useTheme();
  return (
    <DropdownMenuGroup>
      <DropdownMenuLabel>Appearance</DropdownMenuLabel>
      <DropdownMenuRadioGroup value={theme ?? "system"} onValueChange={(value) => setTheme(String(value))}>
        {THEMES.map((t) => (
          <DropdownMenuRadioItem key={t.value} value={t.value} closeOnClick={false}>
            <t.icon />
            {t.label}
          </DropdownMenuRadioItem>
        ))}
      </DropdownMenuRadioGroup>
    </DropdownMenuGroup>
  );
}

function UserMenu({ data }: { data: SidebarData }) {
  const { isMobile } = useSidebar();
  const [signingOut, startSignOut] = useTransition();
  const who = (
    <>
      <Avatar className="size-8 rounded-lg">
        <AvatarFallback className="rounded-lg">{initials(data.user.name)}</AvatarFallback>
      </Avatar>
      <div className="grid flex-1 text-left text-sm leading-tight">
        <span className="truncate font-medium">{data.user.name}</span>
        <span className="truncate text-xs text-muted-foreground">{data.user.email ?? ROLE_LABELS[data.role]}</span>
      </div>
    </>
  );

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <SidebarMenuButton
                size="lg"
                className="data-popup-open:bg-sidebar-accent data-popup-open:text-sidebar-accent-foreground"
              />
            }
          >
            {who}
            <ChevronsUpDown className="ml-auto size-4" />
          </DropdownMenuTrigger>
          <DropdownMenuContent
            className="min-w-56"
            side={isMobile ? "bottom" : "right"}
            align="end"
            sideOffset={4}
          >
            <DropdownMenuGroup>
              <DropdownMenuLabel className="p-0 font-normal">
                <div className="flex items-center gap-2 px-1 py-1.5 text-left text-sm text-foreground">{who}</div>
              </DropdownMenuLabel>
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuGroup>
              <DropdownMenuLabel>
                {data.organization} · {ROLE_LABELS[data.role] ?? data.role}
              </DropdownMenuLabel>
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <ThemeChoice />
            <DropdownMenuSeparator />
            <DropdownMenuItem disabled={signingOut} onClick={() => startSignOut(() => logout())}>
              <LogOut />
              Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  );
}
