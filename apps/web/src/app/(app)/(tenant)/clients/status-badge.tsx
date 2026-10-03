import { getTranslations } from "next-intl/server";

import { Pill, type Tone } from "@/components/pill";

const TONE: Record<"active" | "lead" | "inactive", Tone> = {
  active: "success",
  lead: "primary",
  inactive: "muted",
};

export async function StatusBadge({ status }: { status: keyof typeof TONE }) {
  const t = await getTranslations("clients.statuses");
  return <Pill tone={TONE[status]}>{t(status)}</Pill>;
}
