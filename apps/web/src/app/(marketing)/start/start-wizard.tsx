"use client";

import type { components } from "@business-os/api-client";
import { categories, childrenOf, vertical as findVertical } from "@business-os/verticals";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  ChevronUp,
  Minus,
  Plane,
  Plus,
  ShieldCheck,
  ShoppingBag,
  Sparkles,
  Ticket,
  X,
} from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type ReactNode, useEffect, useId, useRef, useState } from "react";

import { oauthSignIn } from "@/app/(auth)/actions";
import { PROVIDER_MARKS } from "@/components/auth/provider-marks";
import { ModuleIcon } from "@/components/modules/module-icon";
import { OfferPicture } from "@/components/modules/offer-picture";
import { VerticalIcon } from "@/components/vertical-icon";
import type { OAuthProvider } from "@/lib/auth-providers";
import { formatMoney } from "@/lib/money";
import {
  chooseTier,
  CLIENT_SIZES,
  coreTier,
  CURRENCIES,
  type Currency,
  encodePlan,
  isOnce,
  type ModuleKey,
  OFFER_TIERS,
  OFFERS,
  type Offer,
  type PriceLine,
  priceLines,
  type SignupPlan,
  tierOf,
  tierPrice,
  withLocations,
  withoutOrphans,
} from "@/lib/signup-plan";
import { isolate } from "@/lib/bidi";
import { industryTexts } from "@/lib/verticals";

type Catalog = components["schemas"]["Catalog"];

type Step = "account" | "industry" | "business" | "base" | Offer | "summary";
const GROUPS = [
  { key: "business", steps: ["account", "industry", "business"] },
  { key: "plan", steps: ["base"] },
  { key: "extras", steps: ["client_app", "ai", "crm", "whatsapp"] },
  { key: "services", steps: ["pack", "support", "setup"] },
  { key: "summary", steps: ["summary"] },
] as const;

/** The icon of each add-on screen. */
const OFFER_ICON: Record<Offer, ModuleKey> = {
  client_app: "client_app",
  ai: "ai_basic",
  crm: "crm",
  whatsapp: "whatsapp",
  pack: "pack_plus",
  support: "support_priority",
  setup: "setup_guided",
};

type Draft = Omit<SignupPlan, "vertical"> & { vertical: string | null };

type Props = {
  catalogs: Partial<Record<Currency, Catalog>>;
  initial: Draft;
  /** Server-rendered pictures of the add-ons (the marketing site's mocks). */
  illustrations: Partial<Record<Offer, ReactNode>>;
  /** The last day of the free trial if the business is created today (YYYY-MM-DD). */
  trialEndsOn: string;
  /** Signed out with Google or Apple sign-in available: the journey opens with them. */
  providers: OAuthProvider[];
  signedIn: boolean;
  /** Where Google or Apple sign-in comes back to (this page, with its preselections). */
  returnTo: string;
};

/** The sign-up journey: like booking a low-cost flight. The business and its size, then one
 * add-on per screen, each with a basic and a pro choice (2–4 per screen, decision X16) and a
 * live cart, the extras (bundle, support, setup) and a boarding pass; then the payment step. */
export function StartWizard({ catalogs, initial, illustrations, trialEndsOn, providers, signedIn, returnTo }: Props) {
  const t = useTranslations("start");
  const tModules = useTranslations("modules");
  const tAuth = useTranslations("auth.oauth");
  const { text } = industryTexts(useTranslations());
  const locale = useLocale();
  const router = useRouter();
  const steps: Step[] = [...(providers.length > 0 && !signedIn ? (["account"] as const) : []), "industry", "business", "base", ...OFFERS, "summary"];
  const [stepIndex, setStepIndex] = useState(steps[0] === "account" ? 0 : initial.vertical ? 1 : 0);
  // The category whose kinds of business are shown in the industry step (null: all categories).
  const [category, setCategory] = useState<string | null>(findVertical(initial.vertical)?.category ?? null);
  const [draft, setDraft] = useState<Draft>(initial);
  const [notice, setNotice] = useState("");
  const [cartOpen, setCartOpen] = useState(false);
  const [terms, setTerms] = useState(false);
  const [termsError, setTermsError] = useState(false);
  const heading = useRef<HTMLHeadingElement>(null);
  const moved = useRef(false);

  const step = steps[stepIndex];
  const catalog = catalogs[draft.currency] ?? Object.values(catalogs)[0]!;
  const money = (amount: number) => formatMoney(amount, catalog.currency, locale);
  const priceOf = (key: ModuleKey) => catalog.modules.find((m) => m.key === key)?.price ?? 0;
  const { lines, total, once, onceTotal } = priceLines(catalog, draft);

  // Move focus to the new step's heading, so keyboard and screen reader users follow along.
  useEffect(() => {
    if (moved.current) heading.current?.focus();
    moved.current = true;
  }, [stepIndex, category]);

  const go = (index: number) => {
    setStepIndex(Math.min(Math.max(0, index), steps.length - 1));
    setCartOpen(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  const goTo = (target: Step) => go(steps.indexOf(target));
  const next = () => go(stepIndex + 1);
  const back = () => go(stepIndex - 1);

  const label = (key: "core" | ModuleKey) => (key === "core" ? tModules("core") : tModules(`names.${key}`));
  const offerName = (offer: Offer) => t(`offers.${offer}.eyebrow`);
  const tierName = (offer: Offer, tier: string) => t(`offers.${offer}.plans.${tier}.name` as "offers.ai.plans.basic.name");
  const announce = (message: "cart.addedNotice" | "cart.removedNotice", name: string, modules: SignupPlan["modules"]) => {
    const newTotal = priceLines(catalog, { clients: draft.clients, modules }).total;
    setNotice(t(message, { name, total: money(newTotal) }));
  };
  const setTier = (offer: Offer, tier: string | null) => {
    const modules = chooseTier(offer, tier, draft.modules, catalog);
    setDraft({ ...draft, modules });
    const chosen = tier && tierOf(offer, modules);
    announce(chosen ? "cart.addedNotice" : "cart.removedNotice", chosen ? `${offerName(offer)} · ${tierName(offer, chosen)}` : offerName(offer), modules);
  };
  const removeModule = (key: ModuleKey) => {
    const modules = { ...draft.modules };
    delete modules[key];
    const kept = withoutOrphans(modules, catalog);
    setDraft({ ...draft, modules: kept });
    announce("cart.removedNotice", label(key), kept);
  };
  const update = (changes: Partial<Draft>) => {
    const merged = { ...draft, ...changes };
    setDraft({ ...merged, modules: withLocations(merged.modules, merged.locations) });
  };

  const recommends = findVertical(draft.vertical)?.recommendedModules ?? [];
  /** The tier suggested on each screen, from the answers so far (null: none in particular). */
  const suggested: Record<Offer, string | null> = {
    client_app: draft.clients >= 1000 ? "pro" : draft.clients >= 300 || recommends.includes("client_app") ? "basic" : null,
    ai: draft.staff >= 4 ? "pro" : "basic",
    crm: draft.clients <= 300 ? "basic" : "pro",
    whatsapp: recommends.includes("whatsapp") ? "basic" : null,
    pack: draft.locations > 2 || draft.clients >= 1000 ? "max" : draft.clients >= 300 ? "plus" : null,
    support: draft.staff >= 10 || draft.locations > 2 ? "priority" : null,
    setup: draft.clients >= 300 ? "full" : "guided",
  };
  const bestValue: Partial<Record<Offer, string>> = { pack: "max" };

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
    router.push(signedIn ? target : `/signup?next=${encodeURIComponent(target)}`);
  };
  const loginHref = draft.vertical
    ? `/login?next=${encodeURIComponent(`/start/finish?p=${encodePlan({ ...draft, vertical: draft.vertical })}`)}`
    : "/login";

  const headingProps = { ref: heading, tabIndex: -1, className: "text-3xl font-extrabold tracking-tight outline-none sm:text-4xl" };
  const daily = (amount: number) => t("daily", { price: money(Math.round(amount / 30)) });

  // ---- The steps --------------------------------------------------------------------------

  let content: ReactNode;
  if (step === "account") {
    content = (
      <>
        <StepHeading eyebrow={t("account.eyebrow")} title={<h1 {...headingProps}>{t("account.title")}</h1>} subtitle={t("account.subtitle")} />
        <div className="card flex max-w-md flex-col gap-3 p-6">
          {providers.map((provider) => (
            <form key={provider} action={oauthSignIn}>
              <input type="hidden" name="provider" value={provider} />
              <input type="hidden" name="next" value={returnTo} />
              <button type="submit" className="btn-secondary flex w-full items-center justify-center gap-3 px-4 py-3 text-base">
                {PROVIDER_MARKS[provider]()}
                {tAuth(provider)}
              </button>
            </form>
          ))}
          <p className="flex items-center gap-3 text-xs text-muted before:h-px before:flex-1 before:bg-border after:h-px after:flex-1 after:bg-border">
            {tAuth("or")}
          </p>
          <button type="button" onClick={() => goTo(initial.vertical ? "business" : "industry")} className="btn-primary px-4 py-3">
            {t("account.email")}
          </button>
          <p className="text-center text-sm text-muted">
            {t("account.haveAccount")}{" "}
            <Link href={`/login?next=${encodeURIComponent(returnTo)}`} className="font-semibold text-primary underline-offset-4 hover:underline">
              {t("account.login")}
            </Link>
          </p>
        </div>
      </>
    );
  } else if (step === "industry") {
    const choose = (vertical: string) => {
      update({ vertical });
      goTo("business");
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
          title={<h1 {...headingProps}>{t("business.title", { yours: draft.vertical ? text(draft.vertical, "yours") : t("business.yoursGeneric") })}</h1>}
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
            placeholder={t("business.namePlaceholder", { example: draft.vertical ? text(draft.vertical, "example") : t("business.exampleGeneric") })}
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
    const current = CLIENT_SIZES.find((size) => draft.clients <= size) ?? 1500;
    content = (
      <>
        <StepHeading eyebrow={t("base.eyebrow")} title={<h1 {...headingProps}>{t("base.title")}</h1>} subtitle={t("base.pick")} />
        <ul className="enter-items grid grid-cols-2 gap-3 lg:grid-cols-4">
          {CLIENT_SIZES.map((size) => {
            const chosen = size === current;
            const price = coreTier(catalog, size).price;
            return (
              <li key={size}>
                <button
                  type="button"
                  aria-pressed={chosen}
                  onClick={() => update({ clients: size })}
                  className={`relative flex h-full w-full flex-col gap-1 p-4 text-start transition-transform ${chosen ? "card-accent ring-2 ring-primary" : "card card-hover"}`}
                >
                  {chosen && (
                    <span className="flex w-fit items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-xs font-bold text-primary">
                      <Check aria-hidden="true" className="size-3" /> {t("base.current")}
                    </span>
                  )}
                  <span className="font-bold">{t(`business.sizes.${size}`)}</span>
                  <span className="text-xs text-muted">{t("base.clients")}</span>
                  <span className="mt-2 text-2xl font-extrabold">
                    <bdi>{money(price)}</bdi>
                  </span>
                  <span className="text-xs text-muted">{size === 1500 ? t("base.custom") : t("perMonth")}</span>
                </button>
              </li>
            );
          })}
        </ul>
        <div className="card-accent flex flex-col gap-4 p-6">
          <p className="text-sm font-semibold text-primary">{t("base.subtitle")}</p>
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
          <p className="text-sm text-muted">{daily(coreTier(catalog, draft.clients).price)}</p>
        </div>
      </>
    );
  } else if ((OFFERS as readonly string[]).includes(step)) {
    const offer = step as Offer;
    const tiers = OFFER_TIERS[offer];
    const current = tierOf(offer, draft.modules);
    const hasAi = !!(draft.modules.ai_basic || draft.modules.ai_pro);
    const picture = tiers.length === 2 ? (illustrations[offer] ?? (offer === "crm" || offer === "whatsapp" ? <OfferPicture offer={offer} /> : null)) : null;
    content = (
      <>
        <div className="grid items-center gap-6 xl:grid-cols-[1fr_15rem]">
          <StepHeading
            eyebrow={
              <span className="flex items-center gap-2">
                <ModuleIcon module={OFFER_ICON[offer]} size="sm" /> {offerName(offer)}
              </span>
            }
            title={<h1 {...headingProps}>{t(`offers.${offer}.title`)}</h1>}
            subtitle={t(`offers.${offer}.text`)}
          />
          {picture && <div aria-hidden="true" className="hidden max-h-56 overflow-hidden xl:block">{picture}</div>}
        </div>
        <ul className={`enter-items grid gap-4 pt-3 ${tiers.length >= 3 ? "md:grid-cols-3" : "sm:grid-cols-2"}`}>
          {tiers.map((tier, index) => {
            const chosen = tier.modules.length === 0 ? current === null : current === tier.key;
            const price = tierPrice(offer, tier.key, catalog);
            const needsAi = offer === "whatsapp" && tier.key === "pro" && !hasAi;
            const badge = suggested[offer] === tier.key ? t("tier.recommended") : bestValue[offer] === tier.key ? t("tier.bestValue") : null;
            const top = index === tiers.length - 1 && tiers.length > 1;
            return (
              <li key={tier.key}>
                <TierCard
                  icon={tier.modules.at(-1) ?? OFFER_ICON[offer]}
                  muted={tier.modules.length === 0}
                  name={tierName(offer, tier.key)}
                  tagline={t(`offers.${offer}.plans.${tier.key}.tagline` as "offers.ai.plans.basic.tagline")}
                  points={t.raw(`offers.${offer}.plans.${tier.key}.points` as "offers.ai.plans.basic.points") as string[]}
                  badge={badge}
                  premium={top}
                  chosen={chosen}
                  price={
                    tier.modules.length === 0 ? (
                      <span className="text-2xl font-extrabold">{t(isOnce(offer) ? "tier.free" : "tier.included")}</span>
                    ) : (
                      <>
                        <span className="text-2xl font-extrabold">
                          + <bdi>{money(price)}</bdi>
                        </span>
                        <span className="text-sm text-muted">{isOnce(offer) ? t("tier.once") : t("perMonth")}</span>
                      </>
                    )
                  }
                  note={
                    needsAi
                      ? t("tier.needsAi", { price: money(priceOf("ai_basic")) })
                      : tier.modules.length > 0
                        ? isOnce(offer)
                          ? t("tier.onceNote")
                          : daily(price)
                        : null
                  }
                  action={chosen ? t("tier.chosen") : t("tier.choose")}
                  onChoose={() => {
                    setTier(offer, tier.modules.length === 0 ? null : tier.key);
                    next();
                  }}
                />
              </li>
            );
          })}
        </ul>
        {tiers.every((tier) => tier.modules.length > 0) && (
          <button
            type="button"
            onClick={() => {
              if (current) setTier(offer, null);
              next();
            }}
            className="w-fit text-sm font-semibold text-muted underline underline-offset-4 hover:text-foreground"
          >
            {t("tier.noThanks", { name: offerName(offer) })}
          </button>
        )}
      </>
    );
  } else {
    content = (
      <>
        <Confetti />
        <StepHeading eyebrow={t("summary.celebrate")} title={<h1 {...headingProps}>{t("summary.title")}</h1>} subtitle={t("summary.subtitle")} />
        <BoardingPass
          title={t("summary.pass")}
          name={draft.name}
          vertical={draft.vertical ? text(draft.vertical, "name") : ""}
          from={t("summary.from")}
          via={t("summary.trial")}
          to={t("summary.to")}
          date={trialEnds}
        />
        <div className="card flex flex-col gap-5 p-6">
          <div className="flex items-center justify-between gap-3 border-b border-border pb-4">
            <p className="font-bold">
              {t("summary.business", { name: isolate(draft.name), vertical: draft.vertical ? text(draft.vertical, "name") : "" })}
            </p>
            <button type="button" onClick={() => goTo("business")} className="text-sm font-semibold text-primary underline-offset-4 hover:underline">
              {t("summary.edit")}
            </button>
          </div>
          <SummaryLines lines={lines} label={label} money={money} onRemove={removeModule} removeLabel={t("offer.remove")} />
          <div className="flex flex-col gap-2 border-t border-border pt-4">
            <p className="flex items-baseline justify-between gap-3">
              <span className="font-semibold">{t("summary.monthly")}</span>
              <span className="text-2xl font-extrabold">
                <bdi>{money(total)}</bdi>
              </span>
            </p>
            {once.length > 0 && (
              <>
                <p className="pt-2 text-sm font-semibold text-muted">{t("summary.once")}</p>
                <SummaryLines lines={once} label={label} money={money} onRemove={removeModule} removeLabel={t("offer.remove")} />
              </>
            )}
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
  const isOffer = (OFFERS as readonly string[]).includes(step);
  const showContinue = step === "business" || step === "base";
  const percent = Math.round((stepIndex / (steps.length - 1)) * 100);

  return (
    <div className="mx-auto grid w-full max-w-6xl grid-cols-1 gap-8 px-4 pb-32 pt-8 sm:px-6 lg:grid-cols-[1fr_20rem] lg:pb-16">
      <div className="flex min-w-0 flex-col gap-6">
        <nav aria-label={t("progress.label")} className="flex flex-col gap-2">
          <FlightPath percent={percent} />
          <ol className="grid grid-cols-5 gap-2">
            {GROUPS.map((group, index) => (
              <li
                key={group.key}
                aria-current={index === groupIndex ? "step" : undefined}
                className={`truncate text-xs font-semibold ${index <= groupIndex ? "text-foreground" : "text-muted"}`}
              >
                {t(`progress.${group.key}`)}
              </li>
            ))}
          </ol>
          <p className="text-xs text-muted">
            {t("progress.step", { step: stepIndex + 1, total: steps.length })} · {t("progress.flight", { percent })}
          </p>
        </nav>

        {isOffer && (
          <AddOnRail
            current={step as Offer}
            added={(offer) => tierOf(offer, draft.modules) !== null}
            onPick={goTo}
            label={offerName}
            addedLabel={t("offer.added")}
            navLabel={t("progress.extras")}
          />
        )}

        <section key={step} className="enter relative flex flex-col gap-6">
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
          {isOffer && tierOf(step as Offer, draft.modules) !== null && (
            <button type="button" onClick={next} className="btn-primary px-6 py-3">
              {t("next")} <ArrowRight aria-hidden="true" className="size-4 rtl:rotate-180" />
            </button>
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
              {!signedIn && (
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
              )}
            </div>
          )}
        </div>
      </div>

      <Cart
        lines={lines.map((line) => ({ ...line, label: label(line.key) }))}
        once={once.map((line) => ({ ...line, label: label(line.key) }))}
        total={total}
        onceTotal={onceTotal}
        money={money}
        open={cartOpen}
        onToggle={() => setCartOpen((value) => !value)}
        onRemove={removeModule}
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

/** The progress as a flight: a plane moving along the route (decorative; the steps are text). */
function FlightPath({ percent }: { percent: number }) {
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
function TierCard({
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
function BoardingPass({ title, name, vertical, from, via, to, date }: Record<"title" | "name" | "vertical" | "from" | "via" | "to" | "date", string>) {
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
function Confetti() {
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

function SummaryLines({
  lines,
  label,
  money,
  onRemove,
  removeLabel,
}: {
  lines: PriceLine[];
  label: (key: PriceLine["key"]) => string;
  money: (amount: number) => string;
  onRemove: (key: ModuleKey) => void;
  removeLabel: string;
}) {
  return (
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
                onClick={() => onRemove(line.key as ModuleKey)}
                aria-label={`${removeLabel}: ${label(line.key)}`}
                className="flex size-8 items-center justify-center rounded-lg text-muted hover:bg-foreground/5 hover:text-foreground"
              >
                <X aria-hidden="true" className="size-4" />
              </button>
            )}
          </span>
        </li>
      ))}
    </ul>
  );
}

/** The add-ons at a glance: where the person is, what they added, and a way to jump back. */
function AddOnRail({
  current,
  added,
  onPick,
  label,
  addedLabel,
  navLabel,
}: {
  current: Offer;
  added: (offer: Offer) => boolean;
  onPick: (offer: Offer) => void;
  label: (offer: Offer) => string;
  addedLabel: string;
  navLabel: string;
}) {
  return (
    <nav aria-label={navLabel} className="relative -mx-1 overflow-x-auto px-1 pb-1">
      <ol className="flex min-w-max gap-2">
        {OFFERS.map((offer) => {
          const isCurrent = offer === current;
          return (
            <li key={offer}>
              <button
                type="button"
                onClick={() => onPick(offer)}
                aria-current={isCurrent ? "step" : undefined}
                className={`flex items-center gap-2 rounded-full border py-1.5 ps-1.5 pe-3 text-sm font-semibold transition-colors ${
                  isCurrent ? "border-primary bg-primary/10 text-primary" : "border-border bg-surface hover:border-primary/50"
                }`}
              >
                <ModuleIcon module={OFFER_ICON[offer]} size="sm" />
                {label(offer)}
                {added(offer) && (
                  <span className="flex size-5 items-center justify-center rounded-full bg-success text-white">
                    <Check aria-hidden="true" className="size-3" />
                    <span className="sr-only">{addedLabel}</span>
                  </span>
                )}
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

function Badge({ children }: { children: ReactNode }) {
  return (
    <p className="absolute -top-3 start-5 flex items-center gap-1 rounded-full bg-gradient-to-r from-brand-strong-from to-brand-strong-to px-3 py-1 text-xs font-bold text-white shadow">
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

type CartLine = PriceLine & { label: string };

/** The plan so far: a card beside the steps on wide screens, a bar at the bottom on phones. */
function Cart({
  lines,
  once,
  total,
  onceTotal,
  money,
  open,
  onToggle,
  onRemove,
  t,
}: {
  lines: CartLine[];
  once: CartLine[];
  total: number;
  onceTotal: number;
  money: (amount: number) => string;
  open: boolean;
  onToggle: () => void;
  onRemove: (key: ModuleKey) => void;
  t: T;
}) {
  const list = (items: CartLine[]) => (
    <ul className="flex flex-col gap-2">
      {items.map((line) => (
        <li key={line.key} className="group flex animate-[pop_360ms_var(--ease-out)_both] items-center justify-between gap-3 text-sm">
          <span className="flex min-w-0 items-center gap-2">
            {line.key === "core" ? (
              <span aria-hidden="true" className="icon-tile size-8">
                <Check className="size-4" />
              </span>
            ) : (
              <ModuleIcon module={line.key} size="sm" />
            )}
            <span className="truncate">{line.label}</span>
            {line.quantity > 1 && <span className="text-muted" dir="ltr">× {line.quantity}</span>}
          </span>
          <span className="flex items-center gap-1">
            <bdi className="font-semibold">{money(line.amount)}</bdi>
            {line.key !== "core" && line.key !== "extra_location" && (
              <button
                type="button"
                onClick={() => onRemove(line.key as ModuleKey)}
                aria-label={`${t("offer.remove")}: ${line.label}`}
                className="flex size-7 items-center justify-center rounded-lg text-muted hover:bg-foreground/5 hover:text-foreground"
              >
                <X aria-hidden="true" className="size-3.5" />
              </button>
            )}
          </span>
        </li>
      ))}
    </ul>
  );
  const onceBlock = once.length > 0 && (
    <div className="flex flex-col gap-2 border-t border-dashed border-border pt-3">
      <p className="flex items-baseline justify-between gap-2 text-xs font-semibold text-muted">
        <span>{t("cart.once")}</span>
        <bdi>{money(onceTotal)}</bdi>
      </p>
      {list(once)}
    </div>
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
          {list(lines)}
          {lines.length === 1 && once.length === 0 && <p className="text-sm text-muted">{t("cart.emptyHint")}</p>}
          {onceBlock}
          {totals}
          <p className="rounded-xl bg-primary/10 px-3 py-2 text-center text-sm font-semibold text-primary">{t("cart.trial")}</p>
        </div>
      </aside>

      <div className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-surface/95 shadow-[0_-8px_24px_-12px_rgb(0_0_0/0.25)] backdrop-blur lg:hidden">
        {open && (
          <div id="cart-sheet" className="flex max-h-[50vh] flex-col gap-3 overflow-y-auto border-b border-border px-4 py-4">
            {list(lines)}
            {onceBlock}
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
            <span className="text-muted">· {t("cart.items", { count: lines.length + once.length })}</span>
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
