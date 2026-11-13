import { ChevronLeft, Pencil } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";

export function PageHeader({
  title,
  description,
  action,
  back,
}: {
  title: React.ReactNode;
  description?: React.ReactNode;
  action?: React.ReactNode;
  back?: { href: string; label: string };
}) {
  return (
    <div className="grid gap-3 border-b pb-6">
      {back && (
        <Link
          href={back.href}
          className="flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ChevronLeft className="size-4" />
          {back.label}
        </Link>
      )}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="grid min-w-0 gap-1.5">
          <h1 className="text-2xl font-semibold tracking-tight text-balance sm:text-3xl">{title}</h1>
          {description && (
            <p className="max-w-2xl text-sm text-pretty text-muted-foreground sm:text-base">{description}</p>
          )}
        </div>
        {action && <div className="shrink-0">{action}</div>}
      </div>
    </div>
  );
}

export function EditButton({ href, label }: { href: string; label: string }) {
  return (
    <Button
      variant="outline"
      size="sm"
      render={<Link href={href} aria-label={label} />}
      nativeButton={false}
    >
      <Pencil />
      Edit
    </Button>
  );
}

export function TableSkeleton() {
  return <div className="h-40 animate-pulse rounded-xl bg-muted" />;
}
