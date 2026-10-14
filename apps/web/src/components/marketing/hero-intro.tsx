import { BarChart3, CalendarDays, ChevronDown, CreditCard, MessageCircle, UserCog, Users } from "lucide-react";
import { getTranslations } from "next-intl/server";

import { BrandMark } from "@/components/brand-mark";
import { IntroTilt } from "@/components/marketing/intro-tilt";

/** Where each tile starts (scattered in 3D space) before it flies into its place in the grid. */
const ICONS = [CalendarDays, Users, CreditCard, MessageCircle, UserCog, BarChart3] as const;
const SCATTER = [
  { x: "-38vw", y: "-26vh", z: "-420px", rx: "70deg", ry: "-50deg", rz: "-25deg" },
  { x: "30vw", y: "-34vh", z: "-300px", rx: "-60deg", ry: "40deg", rz: "20deg" },
  { x: "42vw", y: "-4vh", z: "240px", rx: "40deg", ry: "70deg", rz: "35deg" },
  { x: "-44vw", y: "18vh", z: "-200px", rx: "-50deg", ry: "-60deg", rz: "-30deg" },
  { x: "-18vw", y: "40vh", z: "160px", rx: "80deg", ry: "30deg", rz: "15deg" },
  { x: "36vw", y: "36vh", z: "-360px", rx: "-70deg", ry: "-35deg", rz: "-20deg" },
] as const;
/** Grid cells around the hub in the middle (a 3 x 3 grid; the hub is cell 5). */
const CELLS = ["col-start-1 row-start-1", "col-start-3 row-start-1", "col-start-1 row-start-2", "col-start-3 row-start-2", "col-start-1 row-start-3", "col-start-3 row-start-3"] as const;

/**
 * The opening scene of the home page: six pieces of a business (calendar, clients, payments,
 * messages, team, reports) fly in from scattered 3D positions and lock around the MyBiz mark.
 * Pure CSS 3D (see `.intro-*` in globals.css), no library; the pointer tilts it a little.
 * Reduced motion shows the finished scene without movement.
 */
export async function HeroIntro() {
  const t = await getTranslations("marketing.intro");
  const tiles = t.raw("tiles") as { title: string; meta: string }[];

  return (
    <section className="section-inverse relative isolate flex min-h-[min(88svh,760px)] w-full flex-col items-center justify-center overflow-hidden bg-navy px-4 pb-16 pt-10 text-white sm:pt-14">
      <div aria-hidden="true" className="mk-grid pointer-events-none absolute inset-0 -z-10" />
      <div aria-hidden="true" className="pointer-events-none absolute -top-32 start-[8%] -z-10 size-[34rem] rounded-full bg-primary/40 blur-[120px]" />
      <div aria-hidden="true" className="pointer-events-none absolute -bottom-40 end-[6%] -z-10 size-[30rem] rounded-full bg-electric/25 blur-[120px]" />

      <div className="intro-copy mx-auto flex max-w-2xl flex-col items-center gap-4 text-center">
        <p className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-4 py-1.5 text-sm font-medium text-white/85 backdrop-blur">
          <span aria-hidden="true" className="size-2 rounded-full bg-electric shadow-[0_0_10px] shadow-electric" />
          {t("eyebrow")}
        </p>
        <p className="text-3xl font-extrabold leading-tight tracking-tight sm:text-5xl">
          {t("title")}{" "}
          <span className="bg-gradient-to-l from-electric to-[#60a5fa] bg-clip-text text-transparent">{t("titleAccent")}</span>
        </p>
        <p className="max-w-lg text-base leading-relaxed text-white/70 sm:text-lg">{t("text")}</p>
      </div>

      <IntroTilt className="intro-scene mt-8 sm:mt-10">
        <div role="img" aria-label={t("sceneLabel")} className="intro-stage">
          <div aria-hidden="true" className="intro-grid grid grid-cols-3 grid-rows-3 gap-3 sm:gap-5">
            {tiles.map((tile, index) => {
              const Icon = ICONS[index] ?? CalendarDays;
              const from = SCATTER[index] ?? SCATTER[0];
              return (
                <div
                  key={tile.title}
                  className={`intro-tile ${CELLS[index] ?? ""}`}
                  style={
                    {
                      "--i": index,
                      "--fx": from.x,
                      "--fy": from.y,
                      "--fz": from.z,
                      "--frx": from.rx,
                      "--fry": from.ry,
                      "--frz": from.rz,
                    } as React.CSSProperties
                  }
                >
                  <div className="intro-tile-face">
                    <span className="icon-tile size-8 sm:size-10">
                      <Icon className="size-4 sm:size-5" />
                    </span>
                    <span className="text-sm font-bold sm:text-base">{tile.title}</span>
                    <span className="text-[11px] text-white/60 sm:text-xs">{tile.meta}</span>
                  </div>
                </div>
              );
            })}
            <div className="intro-hub col-start-2 row-start-2">
              <span className="intro-hub-ring" />
              <span className="intro-hub-ring intro-hub-ring-2" />
              <BrandMark className="intro-hub-mark" />
            </div>
          </div>
        </div>
      </IntroTilt>

      <a
        href="#hero"
        aria-label={t("scroll")}
        className="intro-cue absolute bottom-4 start-1/2 inline-flex size-10 -translate-x-1/2 items-center justify-center rounded-full border border-white/20 text-white/80 transition-colors hover:bg-white/10 rtl:translate-x-1/2"
      >
        <ChevronDown aria-hidden="true" className="size-5" />
      </a>
    </section>
  );
}
