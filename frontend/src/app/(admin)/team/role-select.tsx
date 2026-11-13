"use client";

import { useState, useTransition } from "react";

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ROLE_LABELS } from "@/lib/roles";

import { setMemberRole } from "./actions";

/** Changes a member's role as soon as a new one is picked. */
export function RoleSelect({
  memberId,
  role,
  roles,
  label,
}: {
  memberId: number;
  role: string;
  roles: string[];
  label: string;
}) {
  const [value, setValue] = useState(role);
  const [error, setError] = useState<string>();
  const [pending, startTransition] = useTransition();
  const items = roles.map((r) => ({ value: r, label: ROLE_LABELS[r] }));

  function change(next: string | null) {
    if (!next || next === value) return;
    const previous = value;
    setValue(next);
    setError(undefined);
    startTransition(async () => {
      const result = await setMemberRole(memberId, next);
      if (result.error) {
        setValue(previous);
        setError(result.error);
      }
    });
  }

  return (
    <div className="grid gap-1">
      <Select items={items} value={value} onValueChange={change} disabled={pending}>
        <SelectTrigger size="sm" className="w-32" aria-label={`Role of ${label}`}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {items.map((item) => (
            <SelectItem key={item.value} value={item.value}>
              {item.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}
