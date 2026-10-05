"use client";

import type { components } from "@business-os/api-client";
import { categories, childrenOf, vertical as findVertical } from "@business-os/verticals";
import {
  ArrowLeft,
  ArrowRight,
  Bot,
  Check,
  ChevronUp,
  MessageCircle,
  Minus,
  Plus,
  ShieldCheck,
  ShoppingBag,
  Smartphone,
  Sparkles,
  Target,
  X,
} from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type ReactNode, useEffect, useId, useRef, useState } from "react";

import { OfferPicture } from "@/components/modules/offer-picture";
import { VerticalIcon } from "@/components/vertical-icon";
import { formatMoney } from "@/lib/money";
import {
  CLIENT_SIZES,
  coreTier,
  CURRENCIES,
  type Currency,
  encodePlan,
  type ModuleKey,
  type Modules,
  OFFERS,
  type Offer,
  priceLines,
  type SignupPlan,
  withLocations,
} from "@/lib/signup-plan";
import { isolate } from "@/lib/bidi";
import { industryTexts } from "@/lib/verticals";

type Catalog = components["schemas"]["Catalog"];

const STEPS = ["industry", "business", "base", ...OFFERS, "summary"] as const;
type Step = (typeof STEPS)[number];
const GROUPS = [
  { key: "business", steps: ["industry", "business"] },
  { key: "plan", steps: ["base"] },
  { key: "extras", steps: OFFERS as readonly string[] },
  { key: "summary", steps: ["summary"] },
] as const;

const OFFER_ICONS: Record<Offer, typeof Bot> = { client_app: Smartphone, ai: Bot, crm: Target, whatsapp: MessageCircle };


type Draft = Omit<SignupPlan, "vertical"> & { vertical: string | null };

type Props = {
  catalogs: Partial<Record<Currency, Catalog>>;
  initial: Draft;
  /** Server-rendered pictures of the add-ons (the marketing site's mocks). */
  illustrations: Partial<Record<Offer, ReactNode>>;
  /** The last day of the free trial if the business is created today (YYYY-MM-DD). */
  trialEndsOn: string;
};

/** The sign-up journey: like booking a low-cost flight. The business, the base plan, one
 * add-on per screen with a live cart, and a summary; then an account and the payment step. */
export function StartWizard({ catalogs, initial, illustrations, trialEndsOn }: Props) {
  const t = useTranslations("start");
  const tModules = useTranslations("modules");
  const { text } = industryTexts(useTranslations());
  const locale = useLocale();
  const router = useRouter();
  const [stepIndex, setStepIndex] = useState(initial.vertical ? 1 : 0);
  // The category whose kinds of business are shown in the industry step (null: all categories).
  const [category, setCategory] = useState<string | null>(findVertical(initial.vertical)?.category ?? null);
  const [draft, setDraft] = useState<Draft>(initial);
  const [notice, setNotice] = useState("");
  const [cartOpen, setCartOpen] = useState(false);
  const [terms, setTerms] = useState(false);
  const [termsError, setTermsError] = useState(false);
  const heading = useRef<HTMLHeadingElement>(null);
  const moved = useRef(false);

  const step: Step = STEPS[stepIndex];
  const catalog = catalogs[draft.currency] ?? Object.values(catalogs)[0]!;
  const money = (amount: number) => formatMoney(amount, catalog.currency, locale);
  const priceOf = (key: ModuleKey) => catalog.modules.find((m) => m.key === key)?.price ?? 0;
  const { lines, total } = priceLines(catalog, draft);
  const tier = coreTier(catalog, draft.clients);

  // Move focus to the new step's heading, so keyboard and screen reader users follow along.
  useEffect(() => {
    if (moved.current) heading.current?.focus();
    moved.current = true;
  }, [stepIndex, category]);

  const go = (index: number) => {
    setStepIndex(Math.min(Math.max(0, index), STEPS.length - 1));
    setCartOpen(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  const next = () => go(stepIndex + 1);
  const back = () => go(stepIndex - 1);

  const label = (key: "core" | ModuleKey) => (key === "core" ? tModules("core") : tModules(`names.${key}`));
  const announce = (key: ModuleKey, added: boolean, modules: Modules) => {
    const newTotal = priceLines(catalog, { clients: draft.clients, modules }).total;
    setNotice(t(added ? "cart.addedNotice" : "cart.removedNotice", { name: label(key), total: money(newTotal) }));
  };
  const setModule = (key: ModuleKey, on: boolean) => {
    const modules = { ...draft.modules };
    if (on) modules[key] = 1;
    else delete modules[key];
    if (key === "ai_basic" && on) delete modules.ai_pro;
    if (key === "ai_pro" && on) delete modules.ai_basic;
    setDraft({ ...draft, modules });
    announce(key, on, modules);
  };
  const update = (changes: Partial<Draft>) => {
    const merged = { ...draft, ...changes };
    setDraft({ ...merged, modules: withLocations(merged.modules, merged.locations) });
  };

  const recommends = findVertical(draft.vertical)?.recommendedModules ?? [];
  const recommended: Record<Offer, boolean> = {
    client_app: draft.clients >= 300 || recommends.includes("client_app"),
    ai: true,
    crm: draft.clients <= 300,
    whatsapp: recommends.includes("whatsapp"),
  };
  const recommendedAi: ModuleKey = draft.staff >= 4 ? "ai_pro" : "ai_basic";

  const trialEnds = new Date(`${trialEndsOn}T12:00:00`).toLocaleDateString(locale, {
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  const finish = () => {
    if (!terms) {
      setTermsError(true);
      return;
    }
    if (!draft.vertical) return;
    const plan: SignupPlan = { ...draft, vertical: draft.vertical, name: draft.name.trim() };
    const target = `/start/finish?p=${encodePlan(plan)}`;
    router.push(`/signup?next=${encodeURIComponent(target)}`);
  };
  const loginHref = draft.vertical
    ? `/login?next=${encodeURIComponent(`/start/finish?p=${encodePlan({ ...draft, vertical: draft.vertical })}`)}`
    : "/login";

  const headingProps = { ref: heading, tabIndex: -1, className: "text-3xl font-extrabold tracking-tight outline-none sm:text-4xl" };
  const daily = (amount: number) => t("daily", { price: money(Math.round(amount / 30)) });

  // ---- The steps --------------------------------------------------------------------------

  let content: ReactNode;
  if (step === "industry") {
    const choose = (vertical: string) => {
      update({ vertical });
      next();
    };
    const kinds = category ? childrenOf(category) : [];
    const card = (key: string, chosen: boolean, onClick: () => void, label: string, hint: string) => {
      const { icon, color } = findVertical(key)!;
      return (
        <button
          type="button"
          aria-pressed={chosen}
          onClick={onClick}
          className={`card card-hover flex w-full items-center gap-4 p-5 text-start ${chosen ? "ring-2 ring-primary" : ""}`}
        >
          <span aria-hidden="true" className={`flex size-14 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br text-white shadow-md ${color}`}>
            <VerticalIcon icon={icon} className="size-7" />
          </span>
          <span className="flex flex-col gap-0.5">
            <span className="text-lg font-bold">{label}</span>
            <span className="text-sm text-muted">{hint}</span>
          </span>
        </button>
      );
    };
    content = category ? (
      <>
        <StepHeading
          eyebrow={
            <button type="button" onClick={() => setCategory(null)} className="text-sm font-semibold text-primary underline-offset-4 hover:underline">
              {t("industry.allIndustries")}
            </button>
          }
          title={<h1 {...headingProps}>{t("industry.kindTitle", { name: text(category, "name") })}</h1>}
          subtitle={t("industry.kindSubtitle")}
        />
        <ul className="enter-items grid gap-4 sm:grid-cols-2">
          {kinds.map(({ key }) => (
            <li key={key}>{card(key, draft.vertical === key, () => choose(key), text(key, "name"), text(key, "tagline"))}</li>
          ))}
          <li>
            {card(category, draft.vertical === category, () => choose(category), t("industry.otherKind", { name: text(category, "name") }), text(category, "tagline"))}
          </li>
        </ul>
      </>
    ) : (
      <>
        <StepHeading eyebrow={null} title={<h1 {...headingProps}>{t("industry.title")}</h1>} subtitle={t("industry.subtitle")} />
        <ul className="enter-items grid gap-4 sm:grid-cols-2">
          {categories()
            .filter((c) => c.status !== "planned")
            .map(({ key, children }) => (
              <li key={key}>
                {card(
                  key,
                  findVertical(draft.vertical)?.category === key,
                  () => {
                    if (children.length > 0) setCategory(key);
                    else choose(key);
                  },
                  text(key, "name"),
                  text(key, "tagline"),
                )}
              </li>
            ))}
        </ul>
        <p className="text-sm text-muted">
          {t("industry.missing")}{" "}
          <Link href="/industries" className="font-semibold text-primary underline-offset-4 hover:underline">
            {t("industry.seeAll")}
          </Link>
        </p>
      </>
    );
  } else if (step === "business") {
    content = (
      <>
        <StepHeading
          eyebrow={null}
          title={<h1 {...headingProps}>{t("business.title", { yours: text(draft.vertical ?? "fitness", "yours") })}</h1>}
          subtitle={t("business.subtitle")}
        />
        <form
          id="business-form"
          className="flex flex-col gap-6"
          onSubmit={(event) => {
            event.preventDefault();
            if (draft.name.trim()) next();
          }}
        >
          <TextInput
            label={t("business.name")}
            value={draft.name}
            placeholder={t("business.namePlaceholder", { example: text(draft.vertical ?? "fitness", "example") })}
            onChange={(name) => update({ name })}
          />
          <ChoiceGroup
            legend={t("business.size")}
            hint={t("business.sizeHint")}
            options={CLIENT_SIZES.map((size) => ({ value: String(size), label: t(`business.sizes.${size}`) }))}
            value={String(CLIENT_SIZES.find((size) => draft.clients <= size) ?? 1500)}
            onChange={(value) => update({ clients: Number(value) })}
            columns="grid-cols-2 sm:grid-cols-4"
          />
          <div className="grid gap-6 sm:grid-cols-2">
            <Stepper
              label={t("business.staff")}
              value={draft.staff}
              min={1}
              max={200}
              onChange={(staff) => update({ staff })}
              decrease={t("business.decrease", { label: t("business.staff") })}
              increase={t("business.increase", { label: t("business.staff") })}
            />
            <Stepper
              label={t("business.locations")}
              value={draft.locations}
              min={1}
              max={51}
              onChange={(locations) => update({ locations })}
              decrease={t("business.decrease", { label: t("business.locations") })}
              increase={t("business.increase", { label: t("business.locations") })}
            />
          </div>
          <ChoiceGroup
            legend={t("business.currency")}
            options={CURRENCIES.filter((code) => catalogs[code]).map((code) => ({ value: code, label: t(`business.currencies.${code}`) }))}
            value={draft.currency}
            onChange={(value) => update({ currency: value as Currency })}
            columns="grid-cols-3"
          />
        </form>
      </>
    );
  } else if (step === "base") {
    const extra = draft.modules.extra_location ?? 0;
    content = (
      <>
        <StepHeading eyebrow={t("base.eyebrow")} title={<h1 {...headingProps}>{t("base.title")}</h1>} subtitle={t("base.subtitle")} />
        <div className="card-accent flex flex-col gap-5 p-6">
          <div className="flex flex-wrap items-baseline justify-between gap-3">
            <p className="text-lg font-bold">
              {tier.up_to_clients ? t("base.tier", { count: tier.up_to_clients.toLocaleString(locale) }) : t("base.tierCustom")}
            </p>
            <p className="flex items-baseline gap-1">
              <span className="text-3xl font-extrabold">
                <bdi>{money(tier.price)}</bdi>
              </span>
              <span className="text-sm text-muted">{t("perMonth")}</span>
            </p>
          </div>
          <ul className="grid gap-2 sm:grid-cols-2">
            {(t.raw("base.included") as string[]).map((item) => (
              <li key={item} className="flex items-start gap-2">
                <Check aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-success" />
                {item}
              </li>
            ))}
          </ul>
          {extra > 0 && (
            <p className="flex flex-wrap items-center justify-between gap-2 border-t border-border pt-4 text-sm font-medium">
              <span>{t("base.locations", { count: extra })}</span>
              <bdi>{money(priceOf("extra_location") * extra)}</bdi>
            </p>
          )}
          <p className="text-sm text-muted">{daily(tier.price)}</p>
        </div>
      </>
    );
  } else if (step === "ai") {
    content = (
      <>
        <OfferHeading offer="ai" t={t} headingProps={headingProps} />
        <div className="grid items-center gap-6 lg:grid-cols-[1fr_16rem]">
          <div className="grid gap-4 sm:grid-cols-2">
            {(["ai_basic", "ai_pro"] as const).map((key) => {
              const chosen = !!draft.modules[key];
              return (
                <div key={key} className={`relative flex flex-col gap-3 p-5 ${chosen ? "card-accent ring-2 ring-primary" : "card"}`}>
                  {key === recommendedAi && <Badge>{t("offer.popular")}</Badge>}
                  <h2 className="text-lg font-bold">{t(`offers.ai.tiers.${key}.title`)}</h2>
                  <p className="flex-1 text-sm text-muted">{t(`offers.ai.tiers.${key}.text`)}</p>
                  <p className="flex items-baseline gap-1">
                    <span className="text-2xl font-extrabold">
                      + <bdi>{money(priceOf(key))}</bdi>
                    </span>
                    <span className="text-sm text-muted">{t("perMonth")}</span>
                  </p>
                  <button
                    type="button"
                    aria-pressed={chosen}
                    onClick={() => {
                      if (!chosen) setModule(key, true);
                      next();
                    }}
                    className={chosen ? "btn-secondary px-4 py-2.5" : "btn-primary px-4 py-2.5"}
                  >
                    {chosen ? (
                      <>
                        <Check aria-hidden="true" className="size-4" /> {t("offers.ai.chosen")}
                      </>
                    ) : (
                      t("offers.ai.choose")
                    )}
                  </button>
                </div>
              );
            })}
          </div>
          <div className="hidden lg:block">{illustrations.ai}</div>
        </div>
        <OfferFooter
          added={!!(draft.modules.ai_basic || draft.modules.ai_pro)}
          onRemove={() => setModule(draft.modules.ai_pro ? "ai_pro" : "ai_basic", false)}
          onSkip={() => {
            if (draft.modules.ai_basic || draft.modules.ai_pro) setModule(draft.modules.ai_pro ? "ai_pro" : "ai_basic", false);
            next();
          }}
          t={t}
        />
      </>
    );
  } else if (step === "client_app" || step === "crm" || step === "whatsapp") {
    const key: ModuleKey = step;
    const added = !!draft.modules[key];
    const Icon = OFFER_ICONS[step];
    content = (
      <>
        <OfferHeading offer={step} t={t} headingProps={headingProps} />
        <div className="grid items-center gap-8 lg:grid-cols-2">
          <div className={`relative flex flex-col gap-4 p-6 ${added ? "card-accent ring-2 ring-primary" : "card"}`}>
            {recommended[step] && <Badge>{t("offer.popular")}</Badge>}
            <span aria-hidden="true" className="icon-tile size-12">
              <Icon className="size-6" />
            </span>
            <ul className="flex flex-col gap-2">
              {(t.raw(`offers.${step}.points`) as string[]).map((point) => (
                <li key={point} className="flex items-start gap-2 font-medium">
                  <Check aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-success" />
                  {point}
                </li>
              ))}
            </ul>
            <p className="flex items-baseline gap-1">
              <span className="text-3xl font-extrabold">
                + <bdi>{money(priceOf(key))}</bdi>
              </span>
              <span className="text-sm text-muted">{t("perMonth")}</span>
            </p>
            <p className="-mt-2 text-sm text-muted">{daily(priceOf(key))}</p>
            {added ? (
              <p className="flex items-center gap-2 font-semibold text-success">
                <Check aria-hidden="true" className="size-5" /> {t("offer.added")}
              </p>
            ) : (
              <button
                type="button"
                onClick={() => {
                  setModule(key, true);
                  next();
                }}
                className="btn-primary px-5 py-3 text-lg"
              >
                <Plus aria-hidden="true" className="size-5" /> {t("offer.add")}
              </button>
            )}
          </div>
          <div aria-hidden="true">{illustrations[step] ?? <OfferPicture offer={step} />}</div>
        </div>
        <OfferFooter added={added} onRemove={() => setModule(key, false)} onSkip={next} t={t} />
      </>
    );
  } else {
    content = (
      <>
        <StepHeading eyebrow={null} title={<h1 {...headingProps}>{t("summary.title")}</h1>} subtitle={t("summary.subtitle")} />
        <div className="card flex flex-col gap-5 p-6">
          <div className="flex items-center justify-between gap-3 border-b border-border pb-4">
            <p className="font-bold">
              {t("summary.business", { name: isolate(draft.name), vertical: draft.vertical ? text(draft.vertical, "name") : "" })}
            </p>
            <button type="button" onClick={() => go(1)} className="text-sm font-semibold text-primary underline-offset-4 hover:underline">
              {t("summary.edit")}
            </button>
          </div>
          <ul className="flex flex-col divide-y divide-border">
            {lines.map((line) => (
              <li key={line.key} className="flex items-center justify-between gap-3 py-3">
                <span className="flex items-center gap-2">
                  {label(line.key)}
                  {line.quantity > 1 && <span className="text-sm text-muted" dir="ltr">× {line.quantity}</span>}
                </span>
                <span className="flex items-center gap-2">
                  <bdi className="font-semibold">{money(line.amount)}</bdi>
                  {line.key !== "core" && line.key !== "extra_location" && (
                    <button
                      type="button"
                      onClick={() => setModule(line.key as ModuleKey, false)}
                      aria-label={`${t("offer.remove")}: ${label(line.key)}`}
                      className="flex size-8 items-center justify-center rounded-lg text-muted hover:bg-foreground/5 hover:text-foreground"
                    >
                      <X aria-hidden="true" className="size-4" />
                    </button>
                  )}
                </span>
              </li>
            ))}
          </ul>
          <div className="flex flex-col gap-2 border-t border-border pt-4">
            <p className="flex items-baseline justify-between gap-3">
              <span className="font-semibold">{t("summary.monthly")}</span>
              <span className="text-2xl font-extrabold">
                <bdi>{money(total)}</bdi>
              </span>
            </p>
            <p className="flex items-baseline justify-between gap-3 text-success">
              <span className="font-semibold">{t("summary.today")}</span>
              <span className="text-xl font-extrabold">
                <bdi>{money(0)}</bdi>
              </span>
            </p>
            <p className="text-sm text-muted">{t("summary.trialEnds", { date: trialEnds })}</p>
          </div>
        </div>
        <div className="flex flex-col gap-2">
          <label className="flex items-start gap-3 text-sm">
            <input
              type="checkbox"
              checked={terms}
              onChange={(event) => {
                setTerms(event.target.checked);
                setTermsError(false);
              }}
              aria-invalid={termsError}
              aria-describedby={termsError ? "terms-error" : undefined}
              className="mt-0.5 size-5 accent-[var(--primary)]"
            />
            <span>
              {t.rich("summary.terms", {
                terms: (chunks) => (
                  <Link href="/legal/terms" target="_blank" className="font-semibold text-primary underline underline-offset-4">
                    {chunks}
                  </Link>
                ),
                privacy: (chunks) => (
                  <Link href="/legal/privacy" target="_blank" className="font-semibold text-primary underline underline-offset-4">
                    {chunks}
                  </Link>
                ),
              })}
            </span>
          </label>
          {termsError && (
            <p id="terms-error" role="alert" className="text-sm font-medium text-danger">
              {t("summary.termsRequired")}
            </p>
          )}
        </div>
        <ul className="flex flex-wrap gap-x-5 gap-y-2 text-sm font-medium text-muted">
          {(t.raw("summary.guarantee") as string[]).map((item) => (
            <li key={item} className="flex items-center gap-1.5">
              <ShieldCheck aria-hidden="true" className="size-4 text-success" />
              {item}
            </li>
          ))}
        </ul>
      </>
    );
  }

  // ---- Layout -----------------------------------------------------------------------------

  const groupIndex = GROUPS.findIndex((group) => (group.steps as readonly string[]).includes(step));
  const showContinue = step === "business" || step === "base";

  return (
    <div className="mx-auto grid w-full max-w-6xl gap-8 px-4 pb-32 pt-8 sm:px-6 lg:grid-cols-[1fr_20rem] lg:pb-16">
      <div className="flex min-w-0 flex-col gap-6">
        <nav aria-label={t("progress.label")} className="flex flex-col gap-2">
          <ol className="grid grid-cols-4 gap-2">
            {GROUPS.map((group, index) => (
              <li key={group.key} className="flex flex-col gap-1.5" aria-current={index === groupIndex ? "step" : undefined}>
                <span
                  className={`h-1.5 rounded-full transition-colors duration-500 ${
                    index < groupIndex ? "bg-primary" : index === groupIndex ? "bg-gradient-to-r from-indigo-500 to-fuchsia-500" : "bg-foreground/10"
                  }`}
                />
                <span className={`text-xs font-semibold ${index <= groupIndex ? "text-foreground" : "text-muted"}`}>
                  {t(`progress.${group.key}`)}
                </span>
              </li>
            ))}
          </ol>
          <p className="text-xs text-muted">{t("progress.step", { step: stepIndex + 1, total: STEPS.length })}</p>
        </nav>

        <section key={step} aria-labelledby={undefined} className="enter flex flex-col gap-6">
          {content}
        </section>

        <div className="flex flex-wrap items-center justify-between gap-3">
          {stepIndex > 0 ? (
            <button type="button" onClick={back} className="btn-secondary px-4 py-2.5">
              <ArrowLeft aria-hidden="true" className="size-4 rtl:rotate-180" /> {t("back")}
            </button>
          ) : (
            <span />
          )}
          {showContinue && (
            <button
              type={step === "business" ? "submit" : "button"}
              form={step === "business" ? "business-form" : undefined}
              onClick={step === "business" ? undefined : next}
              className="btn-primary px-6 py-3"
            >
              {t("next")} <ArrowRight aria-hidden="true" className="size-4 rtl:rotate-180" />
            </button>
          )}
          {step === "summary" && (
            <div className="flex flex-col items-end gap-2">
              <button type="button" onClick={finish} className="btn-primary px-6 py-3 text-lg">
                {t("summary.cta")} <ArrowRight aria-hidden="true" className="size-5 rtl:rotate-180" />
              </button>
              <p className="text-sm text-muted">
                {t("summary.haveAccount")}{" "}
                <Link
                  href={loginHref}
                  onClick={(event) => {
                    if (!terms) {
                      event.preventDefault();
                      setTermsError(true);
                    }
                  }}
                  className="font-semibold text-primary underline-offset-4 hover:underline"
                >
                  {t("summary.login")}
                </Link>
              </p>
            </div>
          )}
        </div>
      </div>

      <Cart
        lines={lines.map((line) => ({ ...line, label: label(line.key) }))}
        total={total}
        money={money}
        open={cartOpen}
        onToggle={() => setCartOpen((value) => !value)}
        t={t}
      />
      <p aria-live="polite" className="sr-only">
        {notice}
      </p>
    </div>
  );
}

// ---- Pieces ---------------------------------------------------------------------------------

type T = ReturnType<typeof useTranslations<"start">>;

function StepHeading({ eyebrow, title, subtitle }: { eyebrow: ReactNode; title: ReactNode; subtitle: string }) {
  return (
    <div className="flex flex-col gap-2">
      {eyebrow && <div className="text-sm font-semibold text-primary">{eyebrow}</div>}
      {title}
      <p className="max-w-2xl text-lg text-muted">{subtitle}</p>
    </div>
  );
}

function OfferHeading({ offer, t, headingProps }: { offer: Offer; t: T; headingProps: object }) {
  return (
    <StepHeading
      eyebrow={t(`offers.${offer}.eyebrow`)}
      title={<h1 {...headingProps}>{t(`offers.${offer}.title`)}</h1>}
      subtitle={t(`offers.${offer}.text`)}
    />
  );
}

function OfferFooter({ added, onRemove, onSkip, t }: { added: boolean; onRemove: () => void; onSkip: () => void; t: T }) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      {added ? (
        <>
          <button type="button" onClick={onSkip} className="btn-primary px-6 py-3">
            {t("next")} <ArrowRight aria-hidden="true" className="size-4 rtl:rotate-180" />
          </button>
          <button type="button" onClick={onRemove} className="text-sm font-semibold text-muted underline-offset-4 hover:underline">
            {t("offer.remove")}
          </button>
        </>
      ) : (
        <button type="button" onClick={onSkip} className="btn-secondary px-6 py-3">
          {t("offer.skip")}
        </button>
      )}
    </div>
  );
}

function Badge({ children }: { children: ReactNode }) {
  return (
    <p className="absolute -top-3 start-5 flex items-center gap-1 rounded-full bg-gradient-to-r from-indigo-500 to-fuchsia-500 px-3 py-1 text-xs font-bold text-white shadow">
      <Sparkles aria-hidden="true" className="size-3" />
      {children}
    </p>
  );
}

function TextInput({
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

function ChoiceGroup({
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

function Stepper({
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

type CartLine = { key: string; label: string; quantity: number; amount: number };

/** The plan so far: a card beside the steps on wide screens, a bar at the bottom on phones. */
function Cart({
  lines,
  total,
  money,
  open,
  onToggle,
  t,
}: {
  lines: CartLine[];
  total: number;
  money: (amount: number) => string;
  open: boolean;
  onToggle: () => void;
  t: T;
}) {
  const list = (
    <ul className="flex flex-col gap-2">
      {lines.map((line) => (
        <li key={line.key} className="flex animate-[pop_360ms_var(--ease-out)_both] items-center justify-between gap-3 text-sm">
          <span className="flex items-center gap-1.5">
            <Check aria-hidden="true" className="size-4 shrink-0 text-success" />
            {line.label}
            {line.quantity > 1 && <span className="text-muted" dir="ltr">× {line.quantity}</span>}
          </span>
          <bdi className="font-semibold">{money(line.amount)}</bdi>
        </li>
      ))}
    </ul>
  );
  const totals = (
    <div className="flex flex-col gap-1 border-t border-border pt-3">
      <p className="flex items-baseline justify-between gap-2">
        <span className="text-sm font-semibold">{t("cart.monthly")}</span>
        <span key={total} className="animate-[pop_360ms_var(--ease-out)_both] text-xl font-extrabold">
          <bdi>{money(total)}</bdi>
        </span>
      </p>
      <p className="flex items-baseline justify-between gap-2 text-success">
        <span className="text-sm font-semibold">{t("cart.today")}</span>
        <span className="font-bold">{t("cart.free")}</span>
      </p>
    </div>
  );

  return (
    <>
      <aside aria-label={t("cart.title")} className="hidden lg:block">
        <div className="card sticky top-24 flex flex-col gap-4 p-5">
          <h2 className="flex items-center gap-2 font-bold">
            <ShoppingBag aria-hidden="true" className="size-5 text-primary" />
            {t("cart.title")}
          </h2>
          {list}
          {totals}
          <p className="rounded-xl bg-primary/10 px-3 py-2 text-center text-sm font-semibold text-primary">{t("cart.trial")}</p>
        </div>
      </aside>

      <div className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-surface/95 shadow-[0_-8px_24px_-12px_rgb(0_0_0/0.25)] backdrop-blur lg:hidden">
        {open && (
          <div id="cart-sheet" className="flex max-h-[50vh] flex-col gap-3 overflow-y-auto border-b border-border px-4 py-4">
            {list}
            <p className="text-center text-sm font-semibold text-primary">{t("cart.trial")}</p>
          </div>
        )}
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={open}
          aria-controls="cart-sheet"
          className="flex w-full items-center justify-between gap-3 px-4 py-3"
        >
          <span className="flex items-center gap-2 text-sm font-semibold">
            <ShoppingBag aria-hidden="true" className="size-5 text-primary" />
            {open ? t("cart.hide") : t("cart.show")}
            <span className="text-muted">· {t("cart.items", { count: lines.length })}</span>
          </span>
          <span className="flex items-center gap-2">
            <span key={total} className="animate-[pop_360ms_var(--ease-out)_both] text-lg font-extrabold">
              <bdi>{money(total)}</bdi>
            </span>
            <ChevronUp aria-hidden="true" className={`size-5 transition-transform ${open ? "" : "rotate-180"}`} />
          </span>
        </button>
      </div>
    </>
  );
}
