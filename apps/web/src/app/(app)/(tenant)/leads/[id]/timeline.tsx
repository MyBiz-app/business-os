import type { components } from "@business-os/api-client";
import { ArrowRightLeft, MessageSquare, NotebookPen, Phone, Sparkles, UserCheck, Users } from "lucide-react";
import { getTranslations } from "next-intl/server";

type Activity = components["schemas"]["Activity"];

const ICONS = {
  note: NotebookPen,
  call: Phone,
  message: MessageSquare,
  meeting: Users,
  stage: ArrowRightLeft,
  created: Sparkles,
  converted: UserCheck,
} as const;

export async function Timeline({ activities, locale, timeZone }: { activities: Activity[]; locale: string; timeZone: string }) {
  const t = await getTranslations("leads");
  const when = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short", timeZone });
  return (
    <ol className="flex flex-col">
      {activities.map((activity, index) => {
        const Icon = ICONS[activity.kind];
        const title =
          activity.kind === "stage" && activity.to_stage
            ? t("movedTo", { stage: t(`stages.${activity.to_stage}`) })
            : t(`activities.${activity.kind}`);
        return (
          <li key={activity.id} className="relative flex gap-3 pb-5 last:pb-0">
            {index < activities.length - 1 && (
              <span aria-hidden="true" className="absolute start-[1.05rem] top-9 bottom-0 w-px bg-border" />
            )}
            <span className="icon-tile size-9">
              <Icon aria-hidden="true" className="size-4" />
            </span>
            <div className="flex min-w-0 flex-col gap-0.5 pt-1">
              <p className="text-sm font-medium">{title}</p>
              {activity.note && <p dir="auto" className="whitespace-pre-line text-sm">{activity.note}</p>}
              <p className="text-xs text-muted">
                <time dateTime={activity.occurred_at}>{when.format(new Date(activity.occurred_at))}</time>
                {activity.actor_name && ` · ${activity.actor_name}`}
              </p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
