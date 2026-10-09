"use client";

// The sign-up journey's building blocks: headings, the flight path, the tier cards, the
// boarding pass, confetti and form controls (decision X18 split them out of start-wizard.tsx).

import { Check, Minus, Plane, Plus, Sparkles, Ticket } from "lucide-react";
import { useTranslations } from "next-intl";
import { type ReactNode, useId } from "react";

import { ModuleIcon } from "@/components/modules/module-icon";
import { type ModuleKey, type Offer } from "@/lib/signup-plan";

/** The icon of each add-on screen. */
export const OFFER_ICON: Record<Offer, ModuleKey> = {
  client_app: "client_app",
  ai: "ai_basic",
  crm: "crm",
  whatsapp: "whatsapp",
  pack: "pack_plus",
  support: "support_priority",
  setup: "setup_guided",
};

export type T = ReturnType<typeof useTranslations<"start">>;

export function StepHeading({ eyebrow, title, subtitle }: { eyebrow: ReactNode; title: ReactNode; subtitle: string }) {
  return (
    <div className="flex flex-col gap-2">
      {eyebrow && <div className="text-sm font-semibold text-primary">{eyebrow}</div>}
      {title}
      <p className="max-w-2xl text-lg text-muted">{subtitle}</p>
    </div>
  );
}

/** The progress as a flight: a plane moving along the route (decorative; the steps are text). */
export function FlightPath({ percent }: { percent: number }) {
  return (
    <div aria-hidden="true" className="relative mx-3 h-2 rounded-full bg-foreground/10">
      <div
        className="absolute inset-y-0 start-0 rounded-full bg-gradient-to-r from-brand-from to-brand-to transition-[width] duration-700 ease-out rtl:bg-gradient-to-l"
        style={{ width: `${percent}%` }}
      />
      <span
        className="absolute top-1/2 flex size-7 -translate-y-1/2 items-center justify-center rounded-full bg-surface text-primary shadow-md ring-1 ring-border transition-[inset-inline-start] duration-700 ease-out ltr:-translate-x-1/2 rtl:translate-x-1/2"
        style={{ insetInlineStart: `${percent}%` }}
      >
        <Plane className="size-4 rotate-45 rtl:-rotate-45 rtl:-scale-x-100" />
      </span>
    </div>
  );
}

/** One choice on an add-on screen: what it is, what it costs, and a button to take it. */
export function TierCard({
  icon,
  muted,
  name,
  tagline,
  points,
  badge,
  premium,
  chosen,
  price,
  note,
  action,
  onChoose,
}: {
  icon: string;
  muted: boolean;
  name: string;
  tagline: string;
  points: string[];
  badge: string | null;
  premium: boolean;
  chosen: boolean;
  price: ReactNode;
  note: string | null;
  action: string;
  onChoose: () => void;
}) {
  return (
    <div
      className={`relative flex h-full flex-col gap-4 p-5 transition-transform duration-300 ${
        chosen ? "card-accent ring-2 ring-primary" : premium ? "card-accent card-hover" : "card card-hover"
      } ${premium ? "md:-translate-y-2" : ""}`}
    >
      {badge && <Badge>{badge}</Badge>}
      <div className="flex items-center gap-3">
        {muted ? (
          <span aria-hidden="true" className="icon-tile size-11">
            <Check className="size-5" />
          </span>
        ) : (
          <ModuleIcon module={icon} />
        )}
        <div className="flex min-w-0 flex-col">
          <h2 className="text-lg font-bold">{name}</h2>
          <p className="text-sm text-muted">{tagline}</p>
        </div>
      </div>
      <p className="flex items-baseline gap-1">{price}</p>
      <ul className="flex flex-1 flex-col gap-2 text-sm">
        {points.map((point) => (
          <li key={point} className="flex items-start gap-2">
            <Check aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-success" />
            {point}
          </li>
        ))}
      </ul>
      {note && <p className="text-xs text-muted">{note}</p>}
      <button type="button" aria-pressed={chosen} onClick={onChoose} className={`${chosen || !premium ? "btn-secondary" : "btn-primary"} px-4 py-2.5`}>
        {chosen && <Check aria-hidden="true" className="size-4" />} {action}
      </button>
    </div>
  );
}

/** The plan as a boarding pass, in MyBiz's colors: from today, through the free trial, to the
 * business running. */
export function BoardingPass({ title, name, vertical, from, via, to, date }: Record<"title" | "name" | "vertical" | "from" | "via" | "to" | "date", string>) {
  return (
    <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-brand-strong-from to-brand-strong-to p-6 text-white shadow-xl">
      <div aria-hidden="true" className="absolute -end-10 -top-10 size-40 rounded-full bg-white/10" />
      <p className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide">
        <Ticket aria-hidden="true" className="size-4" /> {title}
      </p>
      <p className="mt-2 text-2xl font-extrabold">
        <bdi>{name}</bdi>
      </p>
      <p className="text-sm font-medium">{vertical}</p>
      <div className="mt-5 flex items-center gap-3 border-t border-dashed border-white/50 pt-5">
        <div className="flex flex-col">
          <span className="text-xs font-medium">{from}</span>
          <span className="font-bold">MyBiz</span>
        </div>
        <div className="flex flex-1 items-center gap-2">
          <span aria-hidden="true" className="h-px flex-1 border-t-2 border-dotted border-white/70" />
          <span className="flex flex-col items-center text-center text-xs font-semibold">
            <Plane aria-hidden="true" className="size-5 rotate-45 rtl:-rotate-45 rtl:-scale-x-100" />
            {via}
          </span>
          <span aria-hidden="true" className="h-px flex-1 border-t-2 border-dotted border-white/70" />
        </div>
        <div className="flex flex-col text-end">
          <span className="text-xs font-medium">{date}</span>
          <span className="font-bold">{to}</span>
        </div>
      </div>
    </div>
  );
}

/** A short, one-time burst of confetti over the summary (none with reduced motion). */
export function Confetti() {
  const colors = ["#6366f1", "#d946ef", "#f59e0b", "#10b981", "#0ea5e9", "#f43f5e"];
  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-x-0 top-0 h-0 overflow-visible motion-reduce:hidden">
      {Array.from({ length: 28 }, (_, i) => (
        <span
          key={i}
          className="absolute top-0 h-3 w-1.5 rounded-sm opacity-0"
          style={{
            insetInlineStart: `${(i * 37) % 100}%`,
            background: colors[i % colors.length],
            animation: `confetti ${1.6 + (i % 5) * 0.25}s var(--ease-out) ${(i % 7) * 0.08}s 1 both`,
          }}
        />
      ))}
    </div>
  );
}

export function Badge({ children }: { children: ReactNode }) {
  return (
    <p className="absolute -top-3 start-5 flex items-center gap-1 rounded-full bg-gradient-to-r from-brand-strong-from to-brand-strong-to px-3 py-1 text-xs font-bold text-white shadow">
      <Sparkles aria-hidden="true" className="size-3" />
      {children}
    </p>
  );
}

export function TextInput({
  label,
  value,
  placeholder,
  onChange,
}: {
  label: string;
  value: string;
  placeholder: string;
  onChange: (value: string) => void;
}) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="font-semibold">
        {label}
      </label>
      <input
        id={id}
        value={value}
        required
        maxLength={120}
        autoComplete="organization"
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        className="control w-full px-4 py-3 text-lg"
      />
    </div>
  );
}

export function ChoiceGroup({
  legend,
  hint,
  options,
  value,
  onChange,
  columns,
}: {
  legend: string;
  hint?: string;
  options: { value: string; label: string }[];
  value: string;
  onChange: (value: string) => void;
  columns: string;
}) {
  const name = useId();
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="font-semibold">{legend}</legend>
      {hint && <p className="text-sm text-muted">{hint}</p>}
      <div className={`mt-1 grid gap-2 ${columns}`}>
        {options.map((option) => (
          <label
            key={option.value}
            className={`flex cursor-pointer items-center justify-center rounded-xl border px-3 py-3 text-center font-semibold transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-primary ${
              value === option.value
                ? "border-primary bg-primary/10 text-primary"
                : "border-border bg-surface hover:border-primary/50"
            }`}
          >
            <input
              type="radio"
              name={name}
              value={option.value}
              checked={value === option.value}
              onChange={() => onChange(option.value)}
              className="sr-only"
            />
            {option.label}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

export function Stepper({
  label,
  value,
  min,
  max,
  onChange,
  decrease,
  increase,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  onChange: (value: number) => void;
  decrease: string;
  increase: string;
}) {
  const id = useId();
  const clamp = (number: number) => Math.min(max, Math.max(min, number));
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="font-semibold">
        {label}
      </label>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => onChange(clamp(value - 1))}
          disabled={value <= min}
          aria-label={decrease}
          className="btn-secondary size-11 shrink-0"
        >
          <Minus aria-hidden="true" className="size-4" />
        </button>
        <input
          id={id}
          type="number"
          inputMode="numeric"
          min={min}
          max={max}
          value={value}
          onChange={(event) => onChange(clamp(Number(event.target.value) || min))}
          className="control w-full min-w-0 px-3 py-2.5 text-center text-lg font-bold"
        />
        <button
          type="button"
          onClick={() => onChange(clamp(value + 1))}
          disabled={value >= max}
          aria-label={increase}
          className="btn-secondary size-11 shrink-0"
        >
          <Plus aria-hidden="true" className="size-4" />
        </button>
      </div>
    </div>
  );
}
