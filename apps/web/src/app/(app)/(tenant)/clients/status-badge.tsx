import { getTranslations } from "next-intl/server";

import { Badge, type BadgeTone } from "@/components/ui/badge";

const TONE: Record<"active" | "lead" | "inactive", BadgeTone> = {
  active: "success",
  lead: "warning",
  inactive: "neutral",
};

export async function StatusBadge({ status }: { status: keyof typeof TONE }) {
  const t = await getTranslations("clients.statuses");
  return (
    <Badge tone={TONE[status]} dot>
      {t(status)}
    </Badge>
  );
}
