// Warnings about the business's space and messages (#104), shared by the web and the apps so
// both say the same thing at the same point: near from 80% of the bundle, over at 100%.

export type UsageWarning = { key: "nearMessages" | "overMessages" | "nearStorage" | "overStorage"; percent: number };

type Usage = { messages: number; messages_included: number; storage_bytes: number; storage_included_bytes: number };

const NEAR = 80;

export function usageWarnings(usage: Usage): UsageWarning[] {
  const warnings: UsageWarning[] = [];
  const check = (used: number, included: number, near: UsageWarning["key"], over: UsageWarning["key"]) => {
    if (included <= 0) return;
    const percent = Math.floor((used / included) * 100);
    if (percent >= 100) warnings.push({ key: over, percent });
    else if (percent >= NEAR) warnings.push({ key: near, percent });
  };
  check(usage.messages, usage.messages_included, "nearMessages", "overMessages");
  check(usage.storage_bytes, usage.storage_included_bytes, "nearStorage", "overStorage");
  return warnings;
}
