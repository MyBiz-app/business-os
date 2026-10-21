"use client";

import {
  ArrowLeftRight,
  BarChart3,
  BellRing,
  CalendarCheck,
  CreditCard,
  Moon,
  MoonStar,
  Play,
  Sparkles,
  Sun,
  Sunrise,
  Sunset,
  UserCog,
  Users,
  Zap,
  type LucideIcon,
} from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { memo, useCallback, useEffect, useRef, useState, useSyncExternalStore, type KeyboardEvent, type PointerEvent } from "react";

import { reducedMotion, subscribeMotion } from "@/components/marketing/demo-stage";
import { formatMoney } from "@/lib/money";

const DAY = 1440;
/** One icon per event in `marketing.intro.events`, in the same order. */
const ICONS: readonly LucideIcon[] = [Sparkles, CalendarCheck, BellRing, Users, ArrowLeftRight, CreditCard, UserCog, Zap, BarChart3, Sparkles];
/** How busy each hour of the day is (0-23): the counters grow along this curve. */
const BUSY = [1, 1, 0.5, 0.3, 0.3, 0.5, 2, 5, 8, 8, 7, 6, 6, 6, 6, 7, 8, 10, 10, 8, 5, 3, 2, 1];
const BUSY_TOTAL = BUSY.reduce((sum, value) => sum + value, 0);
/** What a whole day adds up to; revenue in minor units per currency. */
const TOTALS = { bookings: 38, replies: 112, revenue: { ILS: 624_000, USD: 172_000 } as Record<string, number> };
/** The sky behind the dial through the day: [minute, color]. Mixed in RGB between the stops. */
const SKY: readonly [number, string][] = [
  [0, "#4f46e5"],
  [300, "#6d28d9"],
  [390, "#f472b6"],
  [500, "#a5b4fc"],
  [660, "#38bdf8"],
  [1000, "#22d3ee"],
  [1080, "#818cf8"],
  [1150, "#fb7185"],
  [1230, "#8b5cf6"],
  [1320, "#4f46e5"],
  [DAY, "#4f46e5"],
];

type ClockEvent = { time: string; title: string; meta: string };
type Mode = "intro" | "live" | "manual" | "replay";

const toMinutes = (time: string) => {
  const [hours = 0, minutes = 0] = time.split(":").map(Number);
  return hours * 60 + minutes;
};
const minutesNow = () => {
  const date = new Date();
  return date.getHours() * 60 + date.getMinutes();
};
/** Ticks every 20 seconds so the hand follows the clock once the opening sweep is over. */
const subscribeClock = (notify: () => void) => {
  const timer = window.setInterval(notify, 20_000);
  return () => window.clearInterval(timer);
};
const easeInOut = (x: number) => (x < 0.5 ? 4 * x * x * x : 1 - (-2 * x + 2) ** 3 / 2);

/** The share of a day's activity that has happened by `minute` (0..1). */
function busyShare(minute: number) {
  const hour = Math.min(23, Math.floor(minute / 60));
  let sum = 0;
  for (let index = 0; index < hour; index++) sum += BUSY[index]!;
  sum += BUSY[hour]! * ((minute - hour * 60) / 60);
  return Math.min(1, sum / BUSY_TOTAL);
}

function skyColor(minute: number) {
  const next = SKY.findIndex(([at]) => at >= minute);
  const [toAt, to] = SKY[Math.max(1, next)]!;
  const [fromAt, from] = SKY[Math.max(0, next - 1)]!;
  const t = toAt === fromAt ? 0 : (minute - fromAt) / (toAt - fromAt);
  const channel = (hex: string, index: number) => parseInt(hex.slice(1 + index * 2, 3 + index * 2), 16);
  const mixed = [0, 1, 2].map((index) => Math.round(channel(from, index) + (channel(to, index) - channel(from, index)) * t));
  return `rgb(${mixed.join(" ")})`;
}

function phaseOf(minute: number): { key: "night" | "dawn" | "morning" | "afternoon" | "evening"; Icon: LucideIcon } {
  if (minute < 300 || minute >= 1320) return { key: "night", Icon: MoonStar };
  if (minute < 480) return { key: "dawn", Icon: Sunrise };
  if (minute < 720) return { key: "morning", Icon: Sun };
  if (minute < 1020) return { key: "afternoon", Icon: Sun };
  return { key: "evening", Icon: Sunset };
}

/** A point on the dial at `radius` (of 100) and `share` of the day; rounded so the server and the
 * browser print the same numbers. */
function point(radius: number, share: number) {
  const angle = share * 2 * Math.PI;
  const round = (value: number) => Math.round(value * 100) / 100;
  return { x: round(100 + radius * Math.sin(angle)), y: round(100 - radius * Math.cos(angle)) };
}

/** The 96 quarter-hour ticks and the 00/06/12/18 labels; drawn once. */
const Ticks = memo(function Ticks() {
  return (
    <g>
      {Array.from({ length: 96 }, (_, index) => {
        const hour = index % 4 === 0;
        const from = point(hour ? 80 : 83, index / 96);
        const to = point(86, index / 96);
        return <line key={index} x1={from.x} y1={from.y} x2={to.x} y2={to.y} className={hour ? "dc-tick dc-tick-hour" : "dc-tick"} />;
      })}
      {[0, 6, 12, 18].map((hour) => {
        const at = point(72, hour / 24);
        return (
          <text key={hour} x={at.x} y={at.y} className="dc-hour" dominantBaseline="central" textAnchor="middle">
            {String(hour).padStart(2, "0")}
          </text>
        );
      })}
    </g>
  );
});

/**
 * The home page's opening dial: a 24-hour clock that runs from midnight to the visitor's own time
 * while the business's day happens around it (a lead answered at night, reminders at dawn, a
 * payment at noon) and the counters climb. It can be dragged (mouse), tapped (touch) or moved with
 * the arrow keys, and replayed for the whole day. People who ask for less motion get the finished
 * state at their time, without the sweep.
 */
export function DayClock() {
  const t = useTranslations("marketing.intro");
  const locale = useLocale();
  const events = t.raw("events") as ClockEvent[];
  const currency = t("currency");
  const reduced = useSyncExternalStore(subscribeMotion, reducedMotion, () => false);
  const [swept, setMinute] = useState(0);
  const now = useSyncExternalStore(subscribeClock, minutesNow, () => null);
  const [mode, setMode] = useState<Mode>("intro");
  const frame = useRef(0);
  const dial = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);

  const minute = mode === "live" && now !== null ? now : swept;

  const stop = useCallback(() => cancelAnimationFrame(frame.current), []);
  /** Moves the hand from one time to another over `duration` ms, then calls `done`. */
  const sweep = useCallback(
    (from: number, to: number, duration: number, done: () => void) => {
      stop();
      if (reducedMotion() || duration <= 0) {
        setMinute(to);
        done();
        return;
      }
      const start = performance.now();
      const step = (time: number) => {
        const x = Math.min(1, (time - start) / duration);
        setMinute(from + (to - from) * easeInOut(x));
        if (x < 1) frame.current = requestAnimationFrame(step);
        else done();
      };
      frame.current = requestAnimationFrame(step);
    },
    [stop],
  );

  // The opening sweep from midnight to now; after it the hand follows the real time.
  useEffect(() => {
    const delay = window.setTimeout(
      () => {
        const target = minutesNow();
        sweep(0, target, Math.min(6000, 2200 + (target / DAY) * 4000), () => setMode((value) => (value === "intro" ? "live" : value)));
      },
      reducedMotion() ? 0 : 450,
    );
    return () => {
      window.clearTimeout(delay);
      stop();
    };
  }, [stop, sweep]);

  const timeFormat = new Intl.DateTimeFormat(locale, { hour: "numeric", minute: "2-digit", timeZone: "UTC" });
  const clockText = (value: number) => {
    const whole = Math.min(DAY - 1, Math.floor(value));
    return timeFormat.format(new Date(Date.UTC(2026, 0, 1, Math.floor(whole / 60), whole % 60)));
  };

  const take = (value: number) => {
    stop();
    setMode("manual");
    setMinute(Math.max(0, Math.min(DAY - 1, value)));
  };
  const fromPointer = (event: PointerEvent<HTMLDivElement>) => {
    const box = dial.current?.getBoundingClientRect();
    if (!box) return;
    const angle = Math.atan2(event.clientX - (box.left + box.width / 2), -(event.clientY - (box.top + box.height / 2)));
    const share = (angle / (2 * Math.PI) + 1) % 1;
    take(Math.round((share * DAY) / 5) * 5);
  };
  const onPointerDown = (event: PointerEvent<HTMLDivElement>) => {
    // A finger on the dial must still scroll the page: touch only taps, a mouse or pen drags.
    if (event.pointerType !== "touch") {
      dragging.current = true;
      event.currentTarget.setPointerCapture(event.pointerId);
    }
    fromPointer(event);
  };
  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const steps: Record<string, number> = { ArrowRight: 15, ArrowUp: 15, ArrowLeft: -15, ArrowDown: -15, PageUp: 60, PageDown: -60 };
    if (event.key === "Home") take(0);
    else if (event.key === "End") take(DAY - 1);
    else if (event.key in steps) take(Math.round(minute) + steps[event.key]!);
    else return;
    event.preventDefault();
  };

  const times = events.map((event) => toMinutes(event.time));
  const passed = times.reduce((last, at, index) => (at <= minute ? index : last), -1);
  const current = passed >= 0 ? events[passed]! : { ...t.raw("quiet"), time: "" } as ClockEvent;
  const CurrentIcon = passed >= 0 ? (ICONS[passed] ?? Sparkles) : Moon;
  const phase = phaseOf(minute);
  const day = minute >= 360 && minute < 1170;
  const atNow = now !== null && Math.abs(minute - now) < 1 && mode !== "manual" && mode !== "replay";
  const later = now !== null && minute > now + 1;
  const share = busyShare(minute);
  const revenue = Math.round(((TOTALS.revenue[currency] ?? TOTALS.revenue.ILS!) * share) / 100) * 100;
  const valueText = `${clockText(minute)}, ${current.title}`;

  return (
    <div className="flex w-full flex-col items-center gap-6">
      <div
        className="dc-dial"
        ref={dial}
        role="slider"
        tabIndex={0}
        aria-label={t("dialLabel")}
        aria-describedby="day-clock-hint"
        aria-valuemin={0}
        aria-valuemax={DAY - 1}
        aria-valuenow={Math.round(minute)}
        aria-valuetext={valueText}
        data-day={day}
        style={{ "--p": minute / DAY, "--sky": skyColor(minute) } as React.CSSProperties}
        onPointerDown={onPointerDown}
        onPointerMove={(event) => dragging.current && fromPointer(event)}
        onPointerUp={() => (dragging.current = false)}
        onPointerCancel={() => (dragging.current = false)}
        onKeyDown={onKeyDown}
      >
        <span aria-hidden="true" className="dc-sky" />
        <span aria-hidden="true" className="dc-arc" />
        <svg aria-hidden="true" viewBox="0 0 200 200" className="dc-svg">
          <circle cx="100" cy="100" r="92" className="dc-track" />
          <Ticks />
          {times.map((at, index) => {
            const mark = point(92, at / DAY);
            return (
              <circle
                key={events[index]!.time}
                cx={mark.x}
                cy={mark.y}
                r={index === passed ? 3.4 : 2.4}
                className={index === passed ? "dc-mark dc-mark-now" : at <= minute ? "dc-mark dc-mark-done" : "dc-mark"}
              />
            );
          })}
        </svg>
        <span aria-hidden="true" className="dc-hand">
          <span className="dc-sun" />
        </span>
        <div className="dc-face" aria-hidden="true">
          <span className="inline-flex items-center gap-1.5 text-xs font-medium text-muted sm:text-sm">
            {atNow ? (
              <>
                <span className="dc-live" />
                {t("now")}
              </>
            ) : later ? (
              t("later")
            ) : (
              <>
                <phase.Icon className="size-3.5 sm:size-4" />
                {t(`phases.${phase.key}`)}
              </>
            )}
          </span>
          <span suppressHydrationWarning className="text-4xl font-semibold tracking-tight tabular-nums sm:text-5xl">{clockText(minute)}</span>
          <span key={passed} className="dc-event">
            <span className="dc-event-icon">
              <CurrentIcon className="size-4" />
            </span>
            <span className="text-sm font-semibold leading-snug sm:text-[15px]">{current.title}</span>
            <span className="text-xs leading-snug text-muted sm:text-[13px]">{current.meta}</span>
          </span>
        </div>
      </div>
      <p id="day-clock-hint" className="sr-only">
        {t("dialHint")}
      </p>

      <div className="flex w-full max-w-md flex-col items-center gap-3">
        <p suppressHydrationWarning className="text-xs font-medium text-muted">{t("statsLabel", { time: clockText(minute) })}</p>
        <dl className="dc-stats">
          <div>
            <dt>{t("stats.bookings")}</dt>
            <dd>{Math.round(TOTALS.bookings * share)}</dd>
          </div>
          <div>
            <dt>{t("stats.replies")}</dt>
            <dd>{Math.round(TOTALS.replies * share)}</dd>
          </div>
          <div>
            <dt>{t("stats.revenue")}</dt>
            <dd suppressHydrationWarning>{formatMoney(revenue, currency, locale)}</dd>
          </div>
        </dl>
        <div className="flex flex-wrap items-center justify-center gap-2">
          <button
            type="button"
            className="btn-ghost rounded-full px-4 text-sm"
            onClick={() => {
              setMode("replay");
              sweep(0, DAY - 1, reduced ? 0 : 8000, () => undefined);
            }}
          >
            <Play aria-hidden="true" className="size-4" />
            {t("replay")}
          </button>
          {now !== null && (mode === "manual" || mode === "replay") && (
            <button
              type="button"
              className="btn-ghost rounded-full px-4 text-sm"
              onClick={() => sweep(minute, now, 700, () => setMode("live"))}
            >
              <Sun aria-hidden="true" className="size-4" />
              {t("backToNow")}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
