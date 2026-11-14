import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

export type Tone = "active" | "busy" | "success" | "warning" | "error" | "neutral";

const TONES: Record<Tone, string> = {
  active: "bg-primary/10 text-primary",
  busy: "bg-muted text-muted-foreground",
  success: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
  warning: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
  error: "bg-destructive/10 text-destructive",
  neutral: "bg-muted text-muted-foreground",
};

/** The big round icon at the top of each capture page state. */
export function StatusIcon({
  icon: Icon,
  tone,
  motion,
}: {
  icon: LucideIcon;
  tone: Tone;
  motion?: "spin" | "pulse";
}) {
  return (
    <div className={cn("flex size-16 items-center justify-center rounded-full", TONES[tone])}>
      <Icon
        className={cn("size-7", motion === "spin" && "animate-spin", motion === "pulse" && "animate-pulse")}
        aria-hidden
      />
    </div>
  );
}

/** Icon, heading and explanation, centred. */
export function StatusBlock({
  icon,
  tone,
  motion,
  title,
  children,
}: {
  icon: LucideIcon;
  tone: Tone;
  motion?: "spin" | "pulse";
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-4 text-center">
      <StatusIcon icon={icon} tone={tone} motion={motion} />
      <div className="grid gap-1.5">
        <h1 className="text-xl font-semibold tracking-tight text-balance">{title}</h1>
        <p className="text-sm text-pretty text-muted-foreground">{children}</p>
      </div>
    </div>
  );
}
