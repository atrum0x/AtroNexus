"use server";

import { refresh } from "next/cache";

import { switchTool } from "@/api/generated/endpoints/tools/tools";
import { errorMessage } from "@/lib/action-result";

export async function setToolEnabled(code: string, enabled: boolean): Promise<{ error?: string }> {
  try {
    await switchTool(code, { enabled });
    refresh();
    return {};
  } catch (err) {
    return { error: errorMessage(err) };
  }
}
