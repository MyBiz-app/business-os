"use client";

import type { components } from "@business-os/api-client";
import { BRAND } from "@business-os/i18n/brand";
import { vertical as findVertical } from "@business-os/verticals";
import { ArrowLeft, ArrowRight, Check, ShieldCheck } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type ReactNode, useEffect, useRef, useState } from "react";

import { reportSignupStep } from "./actions";
import { Container } from "@/components/layout/container";
import { ModuleIcon } from "@/components/modules/module-icon";
import { OfferPicture } from "@/components/modules/offer-picture";
import type { ProviderButton } from "@/lib/auth-providers";
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
  priceLines,
  type SignupPlan,
  type SiteFees,
  normalizeWebsiteUrl,
  tierOf,
  tierPrice,
  withLocations,
  withoutOrphans,
} from "@/lib/signup-plan";
import { isolate } from "@/lib/bidi";
import { industryTexts } from "@/lib/verticals";

import { AddOnRail, Cart, SummaryLines } from "./cart";
import { AccountStep, BusinessStep, IndustryStep, PathStep, SiteStep } from "./steps";
import type { Draft } from "./wizard-types";
import {
  BoardingPass,
  Confetti,
    OFFER_ICON,
  StepHeading,
  TierCard,
} from "./journey-pieces";


const SIGNUP_VISIT_KEY = `${BRAND.app.storagePrefix}-signup-visit`;

type Catalog = components["schemas"]["Catalog"] & { website?: SiteFees };

type Step = "path" | "account" | "industry" | "business" | "base" | Offer | "site" | "summary";
const GROUPS = [
  { key: "business", steps: ["path", "account", "industry", "business"] },
  { key: "plan", steps: ["base"] },
  { key: "extras", steps: ["client_app", "ai", "crm", "whatsapp", "site"] },
  { key: "services", steps: ["pack", "support", "setup"] },
  { key: "summary", steps: ["summary"] },
] as const;

/** The numbered dot of a step in the progress column (a tick once the step is done). */
function StepDot({ done, current, index }: { done: boolean; current: boolean; index: number }) {
  return (
    <span
      className={`flex size-8 shrink-0 items-center justify-center rounded-full text-sm font-bold transition-colors ${
        done ? "bg-primary text-on-primary" : current ? "bg-primary/10 text-primary-ink ring-2 ring-primary" : "bg-foreground/8 text-muted"
      }`}
    >
      {done ? <Check aria-hidden="true" className="size-4" /> : index + 1}
    </span>
  );
}

type Props = {
  catalogs: Partial<Record<Currency, Catalog>>;
  initial: Draft;
  /** Server-rendered pictures of the add-ons (the marketing site's mocks). */
  illustrations: Partial<Record<Offer, ReactNode>>;
  /** The last day of the free trial if the business is created today (YYYY-MM-DD). */
  trialEndsOn: string;
  /** Signed out with Google or Apple sign-in available: the journey opens with them. */
  providers: ProviderButton[];
  signedIn: boolean;
  /** Where Google or Apple sign-in comes back to (this page, with its preselections). */
  returnTo: string;
  /** Arrived from the pricing calculator: the plan is chosen already, so after the business
   * details the journey goes straight to the summary. */
  fromCalc?: boolean;
};

/** The sign-up journey: like booking a low-cost flight. The business and its size, then one
 * add-on per screen, each with a basic and a pro choice (2-4 per screen, decision X16) and a
 * live cart, the extras (bundle, support, setup) and a boarding pass; then the payment step. */
export function StartWizard({ catalogs, initial, illustrations, trialEndsOn, providers, signedIn, returnTo, fromCalc = false }: Props) {
  const t = useTranslations("start");
  const tModules = useTranslations("modules");
  const { text } = industryTexts(useTranslations());
  const locale = useLocale();
  const router = useRouter();
  // Links that preselect an industry or come from the calculator already know the answer.
  const asksPath = !initial.vertical && !fromCalc;
  const steps: Step[] = [...(asksPath ? (["path"] as const) : []), ...(providers.some((button) => button.live) && !signedIn ? (["account"] as const) : []), "industry", "business", "base", ...OFFERS.slice(0, 4), "site", ...OFFERS.slice(4), "summary"];
  const [stepIndex, setStepIndex] = useState(steps.indexOf("account") >= 0 || asksPath ? 0 : initial.vertical ? 1 : 0);
  // The category whose kinds of business are shown in the industry step (null: all categories).
  const [category, setCategory] = useState<string | null>(findVertical(initial.vertical)?.category ?? null);
  const [draft, setDraft] = useState<Draft>(initial);
  const [notice, setNotice] = useState("");
  const [cartOpen, setCartOpen] = useState(false);
  const [numberTouched, setNumberTouched] = useState(false);
  const [terms, setTerms] = useState(false);
  const [termsError, setTermsError] = useState(false);
  // Add-ons the person said "no thanks" to, so Continue reads as a choice, not a skip.
  const [declined, setDeclined] = useState<Offer[]>([]);
  const [siteTouched, setSiteTouched] = useState(false);
  const heading = useRef<HTMLHeadingElement>(null);
  const tierList = useRef<HTMLUListElement>(null);
  const termsBox = useRef<HTMLInputElement>(null);
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

  // Tell MyBiz which step this visit reached (a random id for the tab, no personal data), so the
  // console shows where people stop. The add-on screens count as one "extras" step.
  useEffect(() => {
    try {
      let visit = sessionStorage.getItem(SIGNUP_VISIT_KEY);
      if (!visit) {
        visit = crypto.randomUUID();
        sessionStorage.setItem(SIGNUP_VISIT_KEY, visit);
        void reportSignupStep(visit, "signup_started");
      }
      const group = step === "site" ? "extras" : (OFFERS as readonly string[]).includes(step) ? (["pack", "support", "setup"].includes(step) ? "services" : "extras") : step === "path" ? "account" : step;
      void reportSignupStep(visit, "signup_step", group as Parameters<typeof reportSignupStep>[2]);
    } catch {
      // Storage can be blocked; the sign-up works the same without the beacon.
    }
  }, [step]);

  // On a phone the choices swipe sideways: open each screen on the chosen (or suggested) one.
  useEffect(() => {
    const list = tierList.current;
    const card = list?.querySelector<HTMLElement>("[data-chosen=true]") ?? list?.querySelector<HTMLElement>("[data-suggested=true]");
    if (!list || !card || list.scrollWidth <= list.clientWidth) return;
    const rtl = getComputedStyle(list).direction === "rtl";
    const gutter = parseFloat(getComputedStyle(list).scrollPaddingInlineStart) || 0;
    const listBox = list.getBoundingClientRect();
    const cardBox = card.getBoundingClientRect();
    list.scrollLeft += rtl ? cardBox.right - listBox.right + gutter : cardBox.left - listBox.left - gutter;
  }, [stepIndex]);

  const go = (index: number) => {
    setStepIndex(Math.min(Math.max(0, index), steps.length - 1));
    setCartOpen(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  const goTo = (target: Step) => go(steps.indexOf(target));
  const next = () => {
    // "I have a website" needs its address before moving on.
    if (step === "site" && draft.site === "have" && !normalizeWebsiteUrl(draft.websiteUrl ?? "")) {
      setSiteTouched(true);
      return;
    }
    go(stepIndex + 1);
  };
  const back = () => go(stepIndex - 1);

  const label = (key: "core" | "website" | ModuleKey) => (key === "core" ? tModules("core") : key === "website" ? t("site.cartLine") : tModules(`names.${key}`));
  const offerName = (offer: Offer) => t(`offers.${offer}.eyebrow`);
  const tierName = (offer: Offer, tier: string) => t(`offers.${offer}.plans.${tier}.name` as "offers.ai.plans.basic.name");
  const announce = (message: "cart.addedNotice" | "cart.removedNotice", name: string, modules: SignupPlan["modules"]) => {
    const newTotal = priceLines(catalog, { clients: draft.clients, modules, site: draft.site }).total;
    setNotice(t(message, { name, total: money(newTotal) }));
  };
  const setTier = (offer: Offer, tier: string | null) => {
    const modules = chooseTier(offer, tier, draft.modules, catalog);
    setDraft({ ...draft, modules });
    const chosen = tier && tierOf(offer, modules);
    setDeclined((list) => (tier ? list.filter((item) => item !== offer) : [...new Set([...list, offer])]));
    announce(chosen ? "cart.addedNotice" : "cart.removedNotice", chosen ? `${offerName(offer)} · ${tierName(offer, chosen)}` : offerName(offer), modules);
  };
  const removeModule = (key: ModuleKey | "website") => {
    if (key === "website") {
      setDraft({ ...draft, site: "none" });
      setNotice(t("cart.removedNotice", { name: label(key), total: money(priceLines(catalog, { clients: draft.clients, modules: draft.modules }).total) }));
      return;
    }
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
      termsBox.current?.scrollIntoView({ behavior: "smooth", block: "center" });
      termsBox.current?.focus({ preventScroll: true });
      return;
    }
    if (!draft.vertical) return;
    const websiteUrl = draft.site === "have" ? normalizeWebsiteUrl(draft.websiteUrl ?? "") : null;
    const plan: SignupPlan = { ...draft, vertical: draft.vertical, name: draft.name.trim(), websiteUrl: websiteUrl ?? undefined };
    const target = `/start/finish?p=${encodePlan(plan)}`;
    router.push(signedIn ? target : `/signup?next=${encodeURIComponent(target)}`);
  };
  const chosenKind = findVertical(draft.vertical);
  const addOnLabels = lines.filter((line) => line.key !== "core" && line.key !== "extra_location" && line.key !== "website").map((line) => label(line.key));
  const passDetails = [
    ...(draft.entityType ? [{ label: t("summary.passEntity"), value: t(`business.entity.types.${draft.entityType}`) }] : []),
    ...(draft.businessNumber ? [{ label: t("summary.passNumber"), value: draft.businessNumber }] : []),
    ...(chosenKind ? [{ label: t("summary.passCategory"), value: text(chosenKind.category, "name") }] : []),
    { label: t("summary.passSize"), value: t("summary.passSizeValue", { staff: draft.staff, locations: draft.locations }) },
    ...(draft.site === "build" ? [{ label: t("summary.passWebsite"), value: t("summary.passWebsiteBuild") }] : []),
    ...(draft.site === "have" && normalizeWebsiteUrl(draft.websiteUrl ?? "") ? [{ label: t("summary.passWebsite"), value: draft.websiteUrl!.trim() }] : []),
    { label: t("summary.passAddons"), value: addOnLabels.length > 0 ? addOnLabels.join(", ") : t("summary.passNoAddons") },
  ];
  const loginHref = draft.vertical
    ? `/login?next=${encodeURIComponent(`/start/finish?p=${encodePlan({ ...draft, vertical: draft.vertical })}`)}`
    : "/login";

  const headingProps = { ref: heading, tabIndex: -1, className: "text-3xl font-extrabold tracking-tight outline-none sm:text-4xl lg:short:text-3xl" };
  const daily = (amount: number) => t("daily", { price: money(Math.round(amount / 30)) });

  // ---- The steps --------------------------------------------------------------------------

  let content: ReactNode;
  if (step === "path") {
    content = (
      <PathStep
        draft={draft}
        headingProps={headingProps}
        onChoose={(track) => {
          update({ track });
          next();
        }}
      />
    );
  } else if (step === "account") {
    content = <AccountStep providers={providers} returnTo={returnTo} headingProps={headingProps} onEmail={() => goTo(initial.vertical ? "business" : "industry")} />;
  } else if (step === "industry") {
    content = (
      <IndustryStep
        draft={draft}
        category={category}
        setCategory={setCategory}
        headingProps={headingProps}
        onChoose={(vertical) => {
          update({ vertical });
          goTo("business");
        }}
      />
    );
  } else if (step === "business") {
    content = (
      <BusinessStep
        draft={draft}
        catalogCurrencies={CURRENCIES.filter((code) => catalogs[code])}
        update={update}
        numberTouched={numberTouched}
        setNumberTouched={setNumberTouched}
        headingProps={headingProps}
        onContinue={() => (fromCalc ? goTo("summary") : next())}
      />
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
                  className={`btn-plain relative flex h-full w-full flex-col gap-1 p-4 text-start transition-transform ${chosen ? "card-accent ring-2 ring-primary" : "card card-hover"}`}
                >
                  {chosen && (
                    <span className="flex w-fit items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-xs font-bold text-primary-ink">
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
          <p className="text-sm font-semibold text-primary-ink">{t("base.subtitle")}</p>
          <ul className="grid gap-2 sm:grid-cols-2">
            {(t.raw("base.included") as string[]).map((item) => (
              <li key={item} className="flex items-start gap-2">
                <Check aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-success-ink" />
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
  } else if (step === "site") {
    content = <SiteStep draft={draft} update={update} touched={siteTouched} price={catalog.website?.withSystem} headingProps={headingProps} />;
  } else if ((OFFERS as readonly string[]).includes(step)) {
    const offer = step as Offer;
    const tiers = OFFER_TIERS[offer];
    const current = tierOf(offer, draft.modules);
    const hasAi = !!(draft.modules.ai_basic || draft.modules.ai_pro);
    const picture = tiers.length === 2 ? (illustrations[offer] ?? (offer === "crm" || offer === "whatsapp" ? <OfferPicture offer={offer} /> : null)) : null;
    content = (
      <>
        {/* The picture only where there is room for it and the choices below it (wide and tall). */}
        <div className="grid items-center gap-6 xl:[@media(min-height:56rem)]:grid-cols-[1fr_15rem]">
          <StepHeading
            eyebrow={
              <span className="flex items-center gap-2">
                <ModuleIcon module={OFFER_ICON[offer]} size="sm" /> {offerName(offer)}
              </span>
            }
            title={<h1 {...headingProps}>{t(`offers.${offer}.title`)}</h1>}
            subtitle={t(`offers.${offer}.text`)}
          />
          {picture && <div aria-hidden="true" className="hidden max-h-56 overflow-hidden xl:[@media(min-height:56rem)]:block">{picture}</div>}
        </div>
        <ul ref={tierList} className={`enter-items swipe gap-4 [--swipe-gutter:1rem] sm:grid sm:pt-3 ${tiers.length >= 3 ? "sm:grid-cols-2 md:grid-cols-3" : "sm:grid-cols-2"}`}>
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
                  suggested={suggested[offer] === tier.key}
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
                  onChoose={() => setTier(offer, tier.modules.length === 0 ? null : tier.key)}
                />
              </li>
            );
          })}
        </ul>
        {tiers.every((tier) => tier.modules.length > 0) && (
          <button
            type="button"
            aria-pressed={declined.includes(offer)}
            onClick={() => setTier(offer, null)}
            className={`btn-link flex w-fit items-center gap-1.5 text-sm font-semibold underline-offset-4 hover:text-foreground ${
              declined.includes(offer) ? "text-foreground" : "text-muted underline"
            }`}
          >
            {declined.includes(offer) && <Check aria-hidden="true" className="size-4 text-success-ink" />}
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
          icon={findVertical(draft.vertical)?.icon ?? "briefcase"}
          details={passDetails}
        />
        <div className="card flex flex-col gap-5 p-6">
          <div className="flex items-center justify-between gap-3 border-b border-border pb-4">
            <p className="font-bold">
              {t("summary.business", { name: isolate(draft.name), vertical: draft.vertical ? text(draft.vertical, "name") : "" })}
            </p>
            <button type="button" onClick={() => goTo("business")} className="btn-link text-sm font-semibold text-primary-ink underline-offset-4 hover:underline">
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
            <p className="flex items-baseline justify-between gap-3 text-success-ink">
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
              ref={termsBox}
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
                  <Link href="/legal/terms" target="_blank" className="font-semibold text-primary-ink underline underline-offset-4">
                    {chunks}
                  </Link>
                ),
                privacy: (chunks) => (
                  <Link href="/legal/privacy" target="_blank" className="font-semibold text-primary-ink underline underline-offset-4">
                    {chunks}
                  </Link>
                ),
                dpa: (chunks) => (
                  <Link href="/legal/dpa" target="_blank" className="font-semibold text-primary-ink underline underline-offset-4">
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
              <ShieldCheck aria-hidden="true" className="size-4 text-success-ink" />
              {item}
            </li>
          ))}
        </ul>
        <p className="text-sm text-muted">
          <Link href="/legal/cancellation" target="_blank" className="font-semibold text-primary-ink underline underline-offset-4">
            {t("summary.cancellationLink")}
          </Link>
        </p>
      </>
    );
  }

  // ---- Layout -----------------------------------------------------------------------------

  const groupIndex = GROUPS.findIndex((group) => (group.steps as readonly string[]).includes(step));
  const isOffer = (OFFERS as readonly string[]).includes(step);
  const showContinue = step === "business" || step === "base" || step === "site";

  const decided = isOffer && (tierOf(step as Offer, draft.modules) !== null || declined.includes(step as Offer) || OFFER_TIERS[step as Offer].some((tier) => tier.modules.length === 0));
  const arrow = <ArrowRight aria-hidden="true" className="size-4 rtl:rotate-180" />;
  const backButton =
    stepIndex > 0 ? (
      <button type="button" onClick={back} aria-label={t("back")} className="btn-secondary size-11 shrink-0 sm:size-auto sm:px-4 sm:py-2.5">
        <ArrowLeft aria-hidden="true" className="size-4 rtl:rotate-180" /> <span className="max-sm:sr-only">{t("back")}</span>
      </button>
    ) : null;
  const forwardButton = showContinue ? (
    <button
      type={step === "business" ? "submit" : "button"}
      form={step === "business" ? "business-form" : undefined}
      onClick={step === "business" ? undefined : next}
      className="btn-primary px-5 py-2.5 sm:px-6"
    >
      {t("next")} {arrow}
    </button>
  ) : isOffer ? (
    <button type="button" onClick={next} className={`${decided ? "btn-primary" : "btn-secondary"} px-5 py-2.5 sm:px-6`}>
      {decided ? t("next") : t("skip")} {arrow}
    </button>
  ) : step === "summary" ? (
    <button type="button" onClick={finish} className="btn-primary px-5 py-2.5 sm:px-6 sm:text-lg">
      {t("summary.cta")} {arrow}
    </button>
  ) : null;

  return (
    <Container size="default" className="grid grid-cols-1 gap-8 pb-36 pt-6 lg:grid-cols-[17rem_1fr] lg:gap-10 lg:pb-16 lg:pt-10">
      <div className="flex min-w-0 flex-col gap-6 lg:short:gap-4">
        <nav aria-label={t("progress.label")} className="flex flex-col gap-2 lg:hidden">
          <ol className="flex items-center">
            {GROUPS.map((group, index) => {
              const done = index < groupIndex;
              const current = index === groupIndex;
              return (
                <li key={group.key} aria-current={current ? "step" : undefined} className="flex flex-1 items-center gap-2 last:flex-none">
                  <StepDot done={done} current={current} index={index} />
                  <span className={`truncate text-sm font-semibold max-sm:sr-only ${current ? "text-foreground" : "text-muted"}`}>{t(`progress.${group.key}`)}</span>
                  {index < GROUPS.length - 1 && <span aria-hidden="true" className={`h-0.5 min-w-3 flex-1 rounded-full ${done ? "bg-primary" : "bg-foreground/10"}`} />}
                </li>
              );
            })}
          </ol>
          <p className="text-xs text-muted sm:hidden">
            {t("progress.step", { step: stepIndex + 1, total: steps.length })} · {t(`progress.${GROUPS[groupIndex]?.key ?? "summary"}`)}
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

        <section key={step} className="enter relative flex flex-col gap-6 lg:short:gap-4">
          {content}
        </section>

        {/* Back and Continue: a floating bar at the bottom of the steps on wide screens (on phones
            they sit in the bar with the plan, so they are always within reach). */}
        {(backButton || forwardButton) && (
          <div className="sticky bottom-4 z-20 hidden items-center justify-between gap-3 rounded-2xl bg-surface/90 p-3 shadow-lg ring-1 ring-border backdrop-blur lg:flex">
            {backButton ?? <span />}
            {stepIndex > 0 && step !== "summary" && (
              <p className="hidden text-sm text-muted xl:block">{t("progress.step", { step: stepIndex + 1, total: steps.length })}</p>
            )}
            {forwardButton}
          </div>
        )}
        {step === "summary" && !signedIn && (
          <p className="text-sm text-muted lg:text-end">
            {t("summary.haveAccount")}{" "}
            <Link
              href={loginHref}
              onClick={(event) => {
                if (!terms) {
                  event.preventDefault();
                  setTermsError(true);
                }
              }}
              className="font-semibold text-primary-ink underline-offset-4 hover:underline"
            >
              {t("summary.login")}
            </Link>
          </p>
        )}
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
        steps={
          <nav aria-label={t("progress.label")} className="card p-5">
            <ol className="flex flex-col">
              {GROUPS.map((group, index) => {
                const done = index < groupIndex;
                const current = index === groupIndex;
                return (
                  <li key={group.key} aria-current={current ? "step" : undefined} className="flex flex-col">
                    <span className="flex items-center gap-3">
                      <StepDot done={done} current={current} index={index} />
                      <span className={`text-sm font-semibold ${current ? "text-foreground" : "text-muted"}`}>{t(`progress.${group.key}`)}</span>
                    </span>
                    {index < GROUPS.length - 1 && <span aria-hidden="true" className={`ms-4 h-5 w-0.5 rounded-full ${done ? "bg-primary" : "bg-foreground/10"}`} />}
                  </li>
                );
              })}
            </ol>
          </nav>
        }
        actions={
          backButton || forwardButton ? (
            <>
              {backButton}
              {forwardButton}
            </>
          ) : null
        }
      />
      <p aria-live="polite" className="sr-only">
        {notice}
      </p>
    </Container>
  );
}
