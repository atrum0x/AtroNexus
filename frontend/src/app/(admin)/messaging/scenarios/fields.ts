const PLACEHOLDER = /\{([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\}/g;

/** The {fields} in mappings, in order of appearance, without repeats. */
export function fieldsIn(...texts: (string | null | undefined)[]): string[] {
  const found: string[] = [];
  for (const text of texts) {
    for (const m of (text ?? "").matchAll(PLACEHOLDER)) {
      if (!found.includes(m[1])) found.push(m[1]);
    }
  }
  return found;
}

/** {"customer.name": "Acme"} -> {"customer": {"name": "Acme"}}, as IFS would send it. */
export function nest(values: Record<string, string>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [path, value] of Object.entries(values)) {
    const parts = path.split(".");
    let node = out;
    parts.slice(0, -1).forEach((part) => {
      if (typeof node[part] !== "object" || node[part] === null) node[part] = {};
      node = node[part] as Record<string, unknown>;
    });
    node[parts[parts.length - 1]] = value;
  }
  return out;
}

/** The PL/SQL an IFS event action would run for this scenario (top-level fields only). */
export function plsqlCall(code: string, fields: string[]): string {
  const pairs = fields
    .filter((f) => !f.includes("."))
    .slice(0, 10)
    .map((f) => `'${f}', '&${f.replace(/([a-z])([A-Z])/g, "$1_$2").toUpperCase()}'`);
  if (pairs.length === 0) return `C_Atx_Message_Util_API.Send('${code || "SCENARIO_CODE"}');`;
  const indent = " ".repeat(36);
  return (
    `C_Atx_Message_Util_API.Send('${code || "SCENARIO_CODE"}',\n` +
    `   C_Atx_Message_Util_API.Params(${pairs.join(`,\n${indent}`)}));`
  );
}
