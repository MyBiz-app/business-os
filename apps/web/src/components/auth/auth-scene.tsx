import { CalendarCheck, TrendingUp, UserPlus } from "lucide-react";
import { getTranslations } from "next-intl/server";

/** A looping, decorative picture of the product for the sign-in side panel: a day's calendar
 * filling up, a new client arriving and the week's revenue climbing. Pure CSS (see "Auth side
 * panel" in globals.css); it stands still for people who prefer reduced motion. */
export async function AuthScene() {
  const t = await getTranslations("auth");
  return (
    <div aria-hidden="true" className="relative mx-auto h-64 w-full max-w-md shrink-0 select-none [@media(max-height:680px)]:hidden">
      <div className="au-card au-in au-bob absolute inset-x-6 top-6 bottom-4 flex flex-col gap-3 p-4" style={{ animationDelay: "0s, 1.2s" }}>
        <div className="flex items-center justify-between text-xs font-semibold text-white/80">
          <span className="flex items-center gap-2">
            <CalendarCheck className="size-4 text-electric" />
            {t("panel.scene.today")}
          </span>
          <span className="flex gap-1">
            {[0, 1, 2, 3, 4].map((day) => (
              <span key={day} className={`size-1.5 rounded-full ${day === 2 ? "bg-electric" : "bg-white/25"}`} />
            ))}
          </span>
        </div>
        <div className="relative flex flex-1 flex-col justify-around gap-2">
          <span className="au-scan absolute inset-y-0 w-px bg-electric/70" />
          {[
            { width: "62%", offset: "0%", color: "from-primary to-electric", delay: "0.5s" },
            { width: "48%", offset: "30%", color: "from-ai to-primary", delay: "0.8s" },
            { width: "55%", offset: "12%", color: "from-electric to-primary", delay: "1.1s" },
          ].map((slot) => (
            <div key={slot.delay} className="h-5 w-full rounded-md bg-white/5">
              <div
                className={`au-bar h-full rounded-md bg-gradient-to-r ${slot.color}`}
                style={{ width: slot.width, marginInlineStart: slot.offset, animationDelay: slot.delay }}
              />
            </div>
          ))}
        </div>
      </div>

      <div className="au-card au-in au-bob absolute end-0 top-0 flex items-center gap-2 px-3 py-2 text-xs font-semibold" style={{ animationDelay: "0.4s, 2s" }}>
        <span className="flex size-7 items-center justify-center rounded-full bg-gradient-to-br from-ai to-primary">
          <UserPlus className="size-3.5" />
        </span>
        {t("panel.scene.newClient")}
      </div>

      <div className="au-card au-in au-bob absolute bottom-0 start-16 flex items-center gap-3 px-3 py-2" style={{ animationDelay: "0.9s, 2.6s" }}>
        <div className="flex flex-col">
          <span className="text-[0.7rem] text-white/60">{t("panel.scene.revenue")}</span>
          <span className="flex items-center gap-1 text-sm font-bold text-electric">
            <TrendingUp className="size-3.5" />
            +18%
          </span>
        </div>
        <svg viewBox="0 0 80 28" className="h-7 w-20 rtl:-scale-x-100" fill="none">
          <path className="au-draw" pathLength={1} d="M2 24 C14 22 18 12 30 14 S48 22 58 10 S70 4 78 3" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
        </svg>
      </div>
    </div>
  );
}
