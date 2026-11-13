import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

/** The centered card with the logo that every signed-out page uses. */
export function AuthShell({
  title,
  description,
  children,
  footer,
}: {
  title: React.ReactNode;
  description?: React.ReactNode;
  children: React.ReactNode;
  footer?: React.ReactNode;
}) {
  return (
    <main className="flex flex-1 items-center justify-center bg-muted/40 px-4 py-12">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex items-center justify-center gap-2">
          <div className="flex size-8 items-center justify-center rounded-lg bg-primary text-sm font-semibold text-primary-foreground">
            A
          </div>
          <span className="text-lg font-semibold tracking-tight">AtroNexus</span>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-xl">{title}</CardTitle>
            {description && <CardDescription>{description}</CardDescription>}
          </CardHeader>
          <CardContent>{children}</CardContent>
        </Card>

        {footer && <div className="mt-4 text-center text-sm text-muted-foreground">{footer}</div>}
      </div>
    </main>
  );
}

/** A link styled for the text under or inside an auth card. */
export const authLinkClass = "font-medium text-foreground underline-offset-4 hover:underline";
