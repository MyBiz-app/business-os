"use client";

import { Hourglass, Pause, Play } from "lucide-react";
import { useTranslations } from "next-intl";
import Image from "next/image";
import { useEffect, useState, useSyncExternalStore } from "react";

import { reducedMotion, subscribeMotion } from "@/components/marketing/demo-stage";
import { PORTRAITS, type TeamKey } from "@/lib/ai-team";

const SCENE_MS = 6500;
const SCENES = ["secretary", "marketing", "finance", "chief"] as const satisfies readonly TeamKey[];

/** A recorded run of the AI team, like the product tour above it: four scenes, each ending with a
 * card that waits for the owner's approval, to show the AI never acts alone. It can be paused
 * (WCAG 2.2.2), starts paused for people who asked for less motion, and each scene can be picked. */
export function TeamSim() {
  const t = useTranslations("marketing.aiTeam.sim");
  const ta = useTranslations("marketing.aiTeam.agents");
  const [scene, setScene] = useState(0);
  const reduced = useSyncExternalStore(subscribeMotion, reducedMotion, () => false);
  const [manual, setManual] = useState<boolean | null>(null);
  const playing = manual ?? !reduced;

  useEffect(() => {
    if (!playing) return;
    const timer = window.setTimeout(() => setScene((value) => (value + 1) % SCENES.length), SCENE_MS);
    return () => window.clearTimeout(timer);
  }, [playing, scene]);

  const agent = SCENES[scene]!;

  return (
    <div className="flex flex-col gap-6" data-paused={!playing}>
      <div className="relative overflow-hidden rounded-3xl bg-navy p-3 text-white shadow-2xl ring-1 ring-white/10 sm:p-4">
        <div aria-hidden="true" className="pointer-events-none absolute -top-24 start-1/4 size-80 rounded-full bg-ai/30 blur-[100px]" />
        <div className="relative min-h-72 rounded-2xl bg-surface p-5 text-foreground sm:min-h-80 sm:p-7" aria-live="off">
          <div key={`${agent}-${scene}`} className="mx-auto flex max-w-xl flex-col gap-4" aria-hidden="true">
            <div className="mk-rise flex items-center gap-3">
              <Image src={PORTRAITS[agent]} alt="" width={48} height={48} className="size-12 rounded-full object-cover ring-2 ring-border" />
              <div className="flex flex-col">
                <span className="font-bold">{ta(`${agent}.name`)}</span>
                <span className="text-xs text-muted">{ta(`${agent}.role`)}</span>
              </div>
            </div>
            <p className="mk-rise rounded-2xl rounded-ss-md bg-foreground/5 px-4 py-3 text-sm" style={{ animationDelay: "500ms" }}>
              {t(`scenes.${agent}.message`)}
            </p>
            <div className="mk-rise flex flex-col gap-3 rounded-2xl border border-ai/30 bg-ai/[0.07] p-4" style={{ animationDelay: "1600ms" }}>
              <p className="flex items-center gap-1.5 text-xs font-bold text-ai">
                <Hourglass className="size-3.5" />
                {t("waiting")}
              </p>
              <p className="text-sm font-semibold">{t(`scenes.${agent}.card`)}</p>
              <div className="flex gap-2">
                <span className="rounded-full bg-ai px-4 py-1.5 text-xs font-bold text-white">{t("approve")}</span>
                <span className="rounded-full border border-border px-4 py-1.5 text-xs font-semibold text-muted">{t("decline")}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-lg font-semibold" aria-live="polite">{t(`scenes.${agent}.caption`)}</p>
        <div className="flex items-center gap-3">
          <div role="group" aria-label={t("scenesLabel")} className="flex flex-wrap gap-2">
            {SCENES.map((key, index) => (
              <button
                key={key}
                type="button"
                aria-pressed={index === scene}
                onClick={() => setScene(index)}
                className="btn-plain relative h-10 overflow-hidden rounded-full border border-border bg-surface px-4 text-sm font-semibold transition-colors hover:border-primary aria-pressed:border-primary aria-pressed:text-primary-ink"
              >
                {t(`scenes.${key}.tab`)}
                {index === scene && playing && (
                  <span aria-hidden="true" key={scene} className="mk-fill absolute inset-x-0 bottom-0 h-0.5 bg-primary" style={{ ["--scene-ms" as string]: `${SCENE_MS}ms` }} />
                )}
              </button>
            ))}
          </div>
          <button type="button" onClick={() => setManual(!playing)} aria-label={playing ? t("pause") : t("play")} title={playing ? t("pause") : t("play")} className="btn-icon flex size-10 items-center justify-center rounded-full bg-primary text-on-primary">
            {playing ? <Pause aria-hidden="true" className="size-4" /> : <Play aria-hidden="true" className="size-4" />}
          </button>
        </div>
      </div>
      <p className="text-center text-sm text-muted">{t("note")}</p>
    </div>
  );
}
