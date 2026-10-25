import { Check, Dumbbell, HeartPulse, Scissors, Sparkles, Trophy, Flower2 } from "lucide-react";
import { getTranslations } from "next-intl/server";
import Link from "next/link";
import type { CSSProperties } from "react";

import { HeroStageScroll } from "@/components/marketing/hero-stage-scroll";
import { DeviceFrame } from "@/components/ui/device-frame";

const STEPS = 4;
const TILE_ICONS = [Dumbbell, Scissors, HeartPulse, Trophy, Flower2];

type Step = { title: string; text: string };

/**
 * The opening scene of the home page: "your business, on every screen". A tall section holds a
 * pinned stage; scrolling moves through four steps (a client books on the phone, the booking lands
 * on the laptop that opens behind it, the AI team sends reminders, any kind of business fits). All
 * the copy renders on the server; HeroStageScroll only writes --p and data-step, and the motion is
 * CSS (see .hs in globals.css). The devices are decorative; the step cards carry the same facts.
 */
export async function HeroStage() {
  const t = await getTranslations("marketing.intro");
  const steps = t.raw("steps") as Step[];
  const slots = t.raw("phone.slots") as string[];
  const days = t.raw("laptop.days") as string[];
  const events = t.raw("laptop.events") as string[];
  const ai = t.raw("ai") as string[];
  const tiles = t.raw("tiles") as string[];

  return (
    <section id="hero-stage" className="hs" data-step="0" aria-label={t("stageLabel")}>
      <HeroStageScroll targetId="hero-stage" />
      <div className="hs-pin">
        <div aria-hidden="true" className="hs-glow pointer-events-none absolute inset-0 -z-10" />
        <div className="page-gutter mx-auto grid h-full w-full max-w-7xl grid-rows-[auto_minmax(0,1fr)_auto] gap-x-12 gap-y-2 pb-6 pt-4 lg:grid-cols-[minmax(0,26rem)_minmax(0,1fr)] lg:grid-rows-1 lg:items-center lg:py-8">
          <div className="hs-copy flex min-h-0 flex-col justify-center gap-3 text-center lg:gap-6 lg:text-start">
            <div className="hs-head flex flex-col items-center gap-3 lg:items-start">
              <p className="inline-flex items-center gap-2 rounded-full border border-border bg-surface/70 px-3 py-1 text-xs font-medium text-muted sm:text-sm">
                <Sparkles aria-hidden="true" className="size-3.5" />
                {t("eyebrow")}
              </p>
              <p className="text-4xl font-semibold leading-[1.05] tracking-tight sm:text-6xl">
                {t("title")}
                <br />
                <span className="hs-accent">{t("titleAccent")}</span>
              </p>
              <p className="hs-text hidden max-w-md text-base leading-relaxed text-muted lg:block">{t("text")}</p>
              <Link href="/start" className="btn-primary btn-lg hidden rounded-full px-7 lg:inline-flex">
                {t("cta")}
              </Link>
            </div>
            <ol className="hs-cards hidden lg:grid" aria-label={t("stageDescription")}>
              {steps.map((step, i) => (
                <StepCard key={step.title} step={step} i={i} label={t("stepLabel", { n: i + 1, total: STEPS })} />
              ))}
            </ol>
          </div>

          <div className="hs-stage" aria-hidden="true">
            <div className="hs-devices">
              <div className="hs-laptop">
                <DeviceFrame device="laptop" lid="var(--lid)">
                  <div className="hs-crm flex h-full flex-col gap-2 text-[0.6rem] sm:text-xs">
                    <p className="font-semibold">{t("laptop.title")}</p>
                    <div className="grid flex-1 grid-cols-3 gap-2">
                      {days.map((day, d) => (
                        <div key={day} className="flex flex-col gap-1.5 rounded-md border border-border bg-surface/60 p-1.5">
                          <span className="text-muted">{day}</span>
                          {events.slice(d, d + 2).map((e) => (
                            <span key={e} className="rounded bg-primary/10 px-1.5 py-1 text-foreground/80">
                              {e}
                            </span>
                          ))}
                          {d === 2 && (
                            <span className="hs-landing flex items-center justify-between gap-1 rounded bg-primary px-1.5 py-1 text-on-primary">
                              <span>{t("laptop.newBooking")}</span>
                              <span className="rounded-full bg-white/25 px-1">{t("laptop.new")}</span>
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                </DeviceFrame>
              </div>
              <div className="hs-phone">
                <DeviceFrame device="phone" className="!w-full">
                  <div className="relative flex h-full flex-col gap-2 text-[0.62rem] sm:text-xs">
                    <p className="text-[1.05em] font-semibold">{t("phone.title")}</p>
                    <p className="text-muted">{t("phone.today")}</p>
                    {slots.map((time, i) => (
                      <div key={time} className="relative flex items-center justify-between rounded-lg border border-border bg-surface/70 px-2 py-1.5">
                        <span className="font-medium tabular-nums">{time}</span>
                        {i === 1 ? (
                          <span className="hs-book relative inline-grid rounded-full bg-primary px-2 py-0.5 text-on-primary">
                            <span className="hs-book-a">{t("phone.book")}</span>
                            <span className="hs-book-b absolute inset-0 flex items-center justify-center gap-0.5">
                              <Check className="size-3" />
                              {t("phone.booked")}
                            </span>
                          </span>
                        ) : (
                          <span className="rounded-full border border-border px-2 py-0.5 text-muted">{t("phone.book")}</span>
                        )}
                      </div>
                    ))}
                    <p className="hs-toast absolute inset-x-0 bottom-0 flex items-center justify-center gap-1 rounded-xl bg-foreground px-2 py-1.5 text-background">
                      <Check className="size-3" />
                      {t("phone.toast")}
                    </p>
                  </div>
                </DeviceFrame>
              </div>
              {ai.map((line, i) => (
                <p key={line} className="hs-bubble" style={{ "--i": i } as CSSProperties}>
                  <Sparkles className="size-3.5 shrink-0" />
                  {line}
                </p>
              ))}
            </div>
            {tiles.map((name, i) => {
              const Icon = TILE_ICONS[i] ?? Dumbbell;
              return (
                <p key={name} className="hs-tile" style={{ "--i": i } as CSSProperties}>
                  <Icon className="size-4" />
                  {name}
                </p>
              );
            })}
          </div>

          <div className="lg:hidden">
            <ol className="hs-cards grid" aria-label={t("stageDescription")}>
              {steps.map((step, i) => (
                <StepCard key={step.title} step={step} i={i} label={t("stepLabel", { n: i + 1, total: STEPS })} />
              ))}
            </ol>
            <Link href="/start" className="btn-primary hs-cta mt-3 w-full justify-center rounded-full">
              {t("cta")}
            </Link>
          </div>
        </div>
        <p className="hs-cue" aria-hidden="true">
          {t("scroll")}
        </p>
      </div>
    </section>
  );
}

function StepCard({ step, i, label }: { step: Step; i: number; label: string }) {
  return (
    <li className="hs-card" data-i={i} style={{ "--i": i } as CSSProperties}>
      <p className="hs-card-n">
        <span className="tabular-nums">{String(i + 1).padStart(2, "0")}</span>
        <span className="sr-only">{label}</span>
        <span aria-hidden="true">/{String(STEPS).padStart(2, "0")}</span>
      </p>
      <h2 className="text-lg font-semibold leading-snug">{step.title}</h2>
      <p className="hs-card-text text-sm leading-relaxed text-muted">{step.text}</p>
      <span aria-hidden="true" className="hs-bar" />
    </li>
  );
}
