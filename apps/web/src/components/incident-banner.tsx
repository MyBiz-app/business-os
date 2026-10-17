import { TriangleAlert } from "lucide-react";
import { getTranslations } from "next-intl/server";

export type BannerItem = {
  id: string;
  kind: "incident" | "maintenance" | "security";
  title: string;
  body: string;
  statusUrl: string;
};

/** The open incident banners the MyBiz team published: a bar on top of every page until the team
 * resolves them. Shows nothing when all is well. */
export async function IncidentBanner({ items }: { items: BannerItem[] }) {
  if (items.length === 0) return null;
  const t = await getTranslations("app.incidentBanner");
  return (
    <div role="status" className="flex flex-col divide-y divide-border border-b border-border bg-warning/15">
      {items.map((item) => (
        <p key={item.id} className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1 px-4 py-2 text-sm">
          <TriangleAlert aria-hidden="true" className="size-4 shrink-0" />
          <span className="font-semibold">{t(`kinds.${item.kind}`)}</span>
          <span dir="auto">
            {item.title}
            {item.body ? `: ${item.body}` : ""}
          </span>
          {item.statusUrl && (
            <a href={item.statusUrl} target="_blank" rel="noopener noreferrer" className="font-medium underline underline-offset-4">
              {t("status")}
            </a>
          )}
        </p>
      ))}
    </div>
  );
}
