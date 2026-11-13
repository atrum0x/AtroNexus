import "server-only";

import { cache } from "react";

import { listTools } from "@/api/generated/endpoints/tools/tools";
import type { ToolOut } from "@/api/generated/models";

export const CAPTURE = "capture";
export const APPROVALS = "approvals";

/** The tool catalog with this organization's on/off state, fetched once per request. */
export const getTools = cache(async (): Promise<ToolOut[]> => listTools());

export async function isToolEnabled(code: string): Promise<boolean> {
  return (await getTools()).some((t) => t.code === code && t.enabled);
}

/** "$29 / month", plus "+ $0.02 per message" for tools with a per-use price. */
export function formatPrice(tool: ToolOut): { monthly: string; usage?: string } {
  const usd = (value: string) => `$${Number(value).toLocaleString("en-US", { maximumFractionDigits: 2 })}`;
  return {
    monthly: `${usd(tool.monthly_price)} / month`,
    usage: tool.usage_price && tool.usage_unit ? `+ ${usd(tool.usage_price)} per ${tool.usage_unit}` : undefined,
  };
}
