import { CalendarCheck, Sparkles, TrendingUp, Users } from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";

/** Decorative previews of the product. They are pictures, so assistive tech skips them. */

export async function DashboardMock() {
  const t = await getTranslations("marketing.mock");
  const classes = t.raw("classes") as string[];
  const revenue = (await getLocale()) === "he" ? "₪40,520" : "$12,340";
  const bars = [38, 52, 45, 61, 58, 72, 66, 80, 74, 88];
  return (
    <div aria-hidden="true" className="card relative overflow-hidden p-5 shadow-2xl">
      <div className="mb-4 flex items-center gap-1.5">
        <span className="size-2.5 rounded-full bg-red-400" />
        <span className="size-2.5 rounded-full bg-amber-400" />
        <span className="size-2.5 rounded-full bg-emerald-400" />
        <span className="ms-3 text-xs font-medium text-muted">{t("title")}</span>
      </div>
      <div className="grid grid-cols-3 gap-3">
        {[
          { icon: TrendingUp, label: t("revenue"), value: revenue, delta: "+18%" },
          { icon: Users, label: t("members"), value: "129", delta: "+12%" },
          { icon: CalendarCheck, label: t("occupancy"), value: "71%", delta: "+8" },
        ].map(({ icon: Icon, label, value, delta }) => (
          <div key={label} className="rounded-xl border border-border bg-background/60 p-3">
            <span className="icon-tile mb-2 size-7">
              <Icon className="size-3.5" />
            </span>
            <p className="truncate text-[11px] text-muted">{label}</p>
            <p className="text-lg font-bold tabular-nums">{value}</p>
            <p className="text-[11px] font-semibold text-success">{delta}</p>
          </div>
        ))}
      </div>
      <div className="mt-3 grid grid-cols-[1.4fr_1fr] gap-3">
        <div className="flex h-28 items-end gap-1.5 rounded-xl border border-border bg-background/60 p-3" dir="ltr">
          {bars.map((height, index) => (
            <span
              key={index}
              className="flex-1 rounded-t-md bg-gradient-to-t from-primary/50 to-primary [animation:grow_700ms_cubic-bezier(0.22,1,0.36,1)_both] origin-bottom"
              style={{ height: `${height}%`, animationDelay: `${300 + index * 60}ms` }}
            />
          ))}
        </div>
        <div className="flex flex-col gap-1.5 rounded-xl border border-border bg-background/60 p-3">
          <p className="text-[11px] font-semibold">{t("today")}</p>
          {classes.map((name, index) => (
            <div key={name} className="flex items-center gap-2 text-[11px]">
              <span className="font-semibold tabular-nums" dir="ltr">{["07:00", "09:30", "18:00"][index]}</span>
              <span className="h-4 w-0.5 rounded-full" style={{ backgroundColor: ["#ec4899", "#10b981", "#f59e0b"][index] }} />
              <span className="truncate">{name}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export async function ChatMock({ question, answer }: { question: string; answer: string }) {
  return (
    <div aria-hidden="true" className="card flex flex-col gap-3 p-5 shadow-xl">
      <div className="self-end rounded-2xl rounded-ee-md bg-primary px-4 py-2.5 text-sm text-on-primary">{question}</div>
      <div className="flex items-start gap-2">
        <span className="icon-tile size-8 shrink-0">
          <Sparkles className="size-4" />
        </span>
        <div className="rounded-2xl rounded-ss-md bg-foreground/5 px-4 py-2.5 text-sm">{answer}</div>
      </div>
    </div>
  );
}

export async function PhoneMock() {
  const t = await getTranslations("marketing");
  const classes = t.raw("mock.classes") as string[];
  return (
    <div aria-hidden="true" className="mx-auto w-64 rounded-[2.5rem] border-[10px] border-foreground/85 bg-background p-3 shadow-2xl">
      <div className="mx-auto mb-3 h-1.5 w-16 rounded-full bg-foreground/20" />
      <p className="mb-2 text-base font-bold">{t("app.phoneTitle")}</p>
      <div className="mb-3 flex gap-1.5" dir="ltr">
        {["4", "5", "6", "7"].map((day, index) => (
          <span
            key={day}
            className={`flex h-12 flex-1 flex-col items-center justify-center rounded-xl text-sm font-bold ${
              index === 1 ? "bg-primary text-on-primary" : "border border-border"
            }`}
          >
            {day}
          </span>
        ))}
      </div>
      <div className="flex flex-col gap-2">
        {classes.map((name, index) => (
          <div key={name} className="flex items-center gap-2 rounded-2xl border border-border p-2.5">
            <span className="h-9 w-1 rounded-full" style={{ backgroundColor: ["#ec4899", "#10b981", "#f59e0b"][index] }} />
            <div className="min-w-0 flex-1">
              <p className="text-[11px] font-semibold tabular-nums" dir="ltr">{["07:00", "09:30", "18:00"][index]}</p>
              <p className="truncate text-xs font-semibold">{name}</p>
            </div>
            <span
              className={`rounded-lg px-2 py-1 text-[10px] font-bold ${
                index === 0 ? "bg-success text-white dark:text-zinc-950" : "bg-primary text-on-primary"
              }`}
            >
              {index === 0 ? t("app.booked") : t("app.book")}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
