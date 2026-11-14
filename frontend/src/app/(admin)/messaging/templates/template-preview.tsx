import { ExternalLink, Reply } from "lucide-react";

export type PreviewButton = { type: string; text: string; url?: string | null };

const VAR = /\{\{\s*(\d+)\s*\}\}/g;

/** The numbers used as {{n}} in a text, sorted, without repeats. */
export function variableNumbers(text: string | null | undefined): number[] {
  return [...new Set([...(text ?? "").matchAll(VAR)].map((m) => Number(m[1])))].sort((a, b) => a - b);
}

function fill(text: string, values: string[]): string {
  return text.replace(VAR, (whole, n) => values[Number(n) - 1]?.trim() || whole);
}

/** Roughly how WhatsApp shows the message, with example values filled in. */
export function TemplatePreview({
  header,
  body,
  footer,
  buttons,
  bodyExamples,
  headerExample,
}: {
  header?: string | null;
  body: string;
  footer?: string | null;
  buttons: PreviewButton[];
  bodyExamples: string[];
  headerExample?: string | null;
}) {
  return (
    <div className="rounded-xl bg-[#e7ddd3] p-4 dark:bg-[#0b141a]">
      <div className="ml-0 max-w-80 overflow-hidden rounded-lg rounded-tl-none bg-white text-sm text-[#111b21] shadow-sm dark:bg-[#202c33] dark:text-[#e9edef]">
        <div className="grid gap-1 px-3 pt-2 pb-1.5">
          {header && <p className="font-semibold">{fill(header, [headerExample ?? ""])}</p>}
          <p className="whitespace-pre-wrap break-words">
            {body ? fill(body, bodyExamples) : <span className="text-[#667781]">The message text</span>}
          </p>
          {footer && <p className="text-xs text-[#667781] dark:text-[#8696a0]">{footer}</p>}
          <p className="text-right text-[11px] text-[#667781] dark:text-[#8696a0]">12:00</p>
        </div>
        {buttons.map((b, i) => (
          <div
            key={i}
            className="flex items-center justify-center gap-1.5 border-t border-black/10 py-2 text-[13px] font-medium text-[#027eb5] dark:border-white/10 dark:text-[#53bdeb]"
          >
            {b.type === "URL" ? <ExternalLink className="size-3.5" /> : <Reply className="size-3.5" />}
            {b.text || "Button"}
          </div>
        ))}
      </div>
    </div>
  );
}
