import type { JoinConfig } from "@/api/types";

export function summary(c: JoinConfig): string {
  const how: Record<string, string> = {
    inner: "Inner",
    left: "Left",
    right: "Right",
    full: "Full",
    anti: "Anti",
    semi: "Semi",
  };
  const keys = c.keys.map((k) => (k.left === k.right ? k.left : `${k.left} = ${k.right}`)).join(", ");
  return `${how[c.how] ?? c.how} join${keys ? ` por ${keys}` : ""}`;
}
