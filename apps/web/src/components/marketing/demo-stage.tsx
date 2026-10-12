"use client";

import { CalendarCheck, Pause, Play, Sparkles } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState, useSyncExternalStore } from "react";

const SCENE_MS = 5500;
const SCENES = ["schedule", "ai", "reports"] as const;
const BARS = [34, 48, 41, 58, 55, 70, 64, 82, 76, 92];

const MOTION_QUERY = "(prefers-reduced-motion: reduce)";

function subscribeMotion(notify: () => void) {
  const media = window.matchMedia(MOTION_QUERY);
  media.addEventListener("change", notify);
  window.addEventListener("a11y-change", notify);
  return () => {
    media.removeEventListener("change", notify);
    window.removeEventListener("a11y-change", notify);
  };
}

/** True when the device or the person's accessibility choice asks for less motion. */
function reducedMotion() {
  return window.matchMedia(MOTION_QUERY).matches || document.documentElement.dataset.motion === "reduce";
}

/** A short looping product tour built from the real screens' look: booking a class, asking the
 * AI, reading the numbers. It can be paused (WCAG 2.2.2), starts paused for people who asked
 * for less motion, and every scene can be picked by hand. */
export function DemoStage() {
  const t = useTranslations("marketing.home.demo");
  const tm = useTranslations("marketing");
  const locale = useLocale();
  const [scene, setScene] = useState(0);
  const reduced = useSyncExternalStore(subscribeMotion, reducedMotion, () => false);
  const [manual, setManual] = useState<boolean | null>(null);
  const playing = manual ?? !reduced;

  useEffect(() => {
    if (!playing) return;
    const timer = window.setTimeout(() => setScene((value) => (value + 1) % SCENES.length), SCENE_MS);
    return () => window.clearTimeout(timer);
  }, [playing, scene]);

  const classes = tm.raw("mock.classes") as string[];
  const revenue = locale === "he" ? "₪40,520" : "$12,340";
  const current = SCENES[scene]!;

  return (
    <div className="flex flex-col gap-6" data-paused={!playing}>
      <div className="relative overflow-hidden rounded-3xl bg-navy p-3 text-white shadow-2xl ring-1 ring-white/10 sm:p-4">
        <div aria-hidden="true" className="pointer-events-none absolute -top-24 start-1/4 size-80 rounded-full bg-primary/30 blur-[100px]" />
        <div className="relative mb-3 flex items-center gap-1.5 px-1" aria-hidden="true">
          <span className="size-2.5 rounded-full bg-red-400" />
          <span className="size-2.5 rounded-full bg-amber-400" />
          <span className="size-2.5 rounded-full bg-emerald-400" />
        </div>
        <div className="relative min-h-72 rounded-2xl bg-surface p-5 text-foreground sm:min-h-80 sm:p-7" aria-live="off">
          <div key={`${current}-${scene}`} className="flex h-full flex-col gap-4" aria-hidden="true">
            {current === "schedule" && (
              <>
                <p className="mk-rise text-sm font-semibold text-muted">{tm("mock.today")}</p>
                <ul className="flex flex-col gap-3">
                  {classes.map((name, index) => (
                    <li key={name} className="mk-rise flex items-center gap-3 rounded-xl border border-border bg-background px-4 py-3" style={{ animationDelay: `${150 + index * 180}ms` }}>
                      <span className="font-semibold tabular-nums" dir="ltr">{["07:00", "09:30", "18:00"][index]}</span>
                      <span className="h-6 w-1 rounded-full" style={{ backgroundColor: ["#2563eb", "#06b6d4", "#7c3aed"][index] }} />
                      <span className="flex-1 truncate font-medium">{name}</span>
                      <span className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-bold ${index === 1 ? "mk-rise bg-success/15 text-[#15803d] dark:text-success" : "bg-primary/10 text-primary"}`} style={index === 1 ? { animationDelay: "1400ms" } : undefined}>
                        {index === 1 && <CalendarCheck className="size-3.5" />}
                        {index === 1 ? t("booked") : t("open")}
                      </span>
                    </li>
                  ))}
                </ul>
              </>
            )}
            {current === "ai" && (
              <div className="mx-auto flex w-full max-w-xl flex-col gap-3 pt-2">
                <div className="mk-rise self-end rounded-2xl rounded-ee-md bg-ai px-4 py-3 text-sm text-white">{tm("ai.q")}</div>
                <div className="mk-rise flex items-start gap-2" style={{ animationDelay: "900ms" }}>
                  <span className="flex size-8 shrink-0 items-center justify-center rounded-xl bg-ai/10 text-ai">
                    <Sparkles className="size-4" />
                  </span>
                  <div className="rounded-2xl rounded-ss-md bg-foreground/5 px-4 py-3 text-sm">{tm("ai.a")}</div>
                </div>
                <div className="mk-rise flex items-center gap-2 self-center rounded-full border border-ai/30 bg-ai/10 px-4 py-1.5 text-xs font-semibold text-ai" style={{ animationDelay: "1900ms" }}>
                  {t("approve")}
                </div>
              </div>
            )}
            {current === "reports" && (
              <>
                <div className="mk-rise flex items-baseline justify-between">
                  <p className="text-sm font-semibold text-muted">{tm("mock.revenue")}</p>
                  <p className="text-3xl font-extrabold tabular-nums sm:text-4xl"><bdi>{revenue}</bdi> <span className="text-base font-bold text-success">+18%</span></p>
                </div>
                <div className="flex h-40 items-end gap-2 rounded-xl border border-border bg-background p-4 sm:h-48" dir="ltr">
                  {BARS.map((height, index) => (
                    <span key={index} className="mk-grow flex-1 rounded-t-md bg-gradient-to-t from-primary to-electric" style={{ height: `${height}%`, animationDelay: `${index * 70}ms` }} />
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-lg font-semibold" aria-live="polite">{t(`scenes.${current}`)}</p>
        <div className="flex items-center gap-3">
          <div role="group" aria-label={t("scenesLabel")} className="flex gap-2">
            {SCENES.map((key, index) => (
              <button
                key={key}
                type="button"
                aria-pressed={index === scene}
                onClick={() => setScene(index)}
                className="relative h-10 overflow-hidden rounded-full border border-border bg-surface px-4 text-sm font-semibold transition-colors hover:border-primary aria-pressed:border-primary aria-pressed:text-primary"
              >
                {t(`tabs.${key}`)}
                {index === scene && playing && (
                  <span aria-hidden="true" key={scene} className="mk-fill absolute inset-x-0 bottom-0 h-0.5 bg-primary" style={{ ["--scene-ms" as string]: `${SCENE_MS}ms` }} />
                )}
              </button>
            ))}
          </div>
          <button type="button" onClick={() => setManual(!playing)} aria-label={playing ? t("pause") : t("play")} title={playing ? t("pause") : t("play")} className="flex size-10 items-center justify-center rounded-full bg-primary text-on-primary">
            {playing ? <Pause aria-hidden="true" className="size-4" /> : <Play aria-hidden="true" className="size-4" />}
          </button>
        </div>
      </div>
    </div>
  );
}
