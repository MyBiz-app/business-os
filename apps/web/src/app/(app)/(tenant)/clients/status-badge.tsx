import { getTranslations } from "next-intl/server";

const TONE = {
  active: "bg-success/15 text-success",
  lead: "bg-primary/15 text-primary",
  inactive: "bg-border text-muted",
} as const;

export async function StatusBadge({ status }: { status: keyof typeof TONE }) {
  const t = await getTranslations("clients.statuses");
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${TONE[status]}`}>
      {t(status)}
    </span>
  );
}
