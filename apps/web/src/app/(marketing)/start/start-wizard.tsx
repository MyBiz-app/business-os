"use client";

import type { components } from "@business-os/api-client";
import { categories, childrenOf, vertical as findVertical } from "@business-os/verticals";
import { ArrowLeft, ArrowRight, Check, ShieldCheck } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type ReactNode, useEffect, useRef, useState } from "react";

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
  priceLines,
  type SignupPlan,
  tierOf,
  tierPrice,
  withLocations,
  withoutOrphans,
} from "@/lib/signup-plan";
import { isolate } from "@/lib/bidi";
import { industryTexts } from "@/lib/verticals";

import { AddOnRail, Cart, SummaryLines } from "./cart";
import {
  BoardingPass,
  ChoiceGroup,
  Confetti,
  FlightPath,
  OFFER_ICON,
  StepHeading,
  Stepper,
  TextInput,
  TierCard,
} from "./journey-pieces";

type Catalog = components["schemas"]["Catalog"];

type Step = "account" | "industry" | "business" | "base" | Offer | "summary";
const GROUPS = [
  { key: "business", steps: ["account", "industry", "business"] },
  { key: "plan", steps: ["base"] },
  { key: "extras", steps: ["client_app", "ai", "crm", "whatsapp"] },
  { key: "services", steps: ["pack", "support", "setup"] },
  { key: "summary", steps: ["summary"] },
] as const;

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
  // Add-ons the person said "no thanks" to, so Continue reads as a choice, not a skip.
  const [declined, setDeclined] = useState<Offer[]>([]);
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
    setDeclined((list) => (tier ? list.filter((item) => item !== offer) : [...new Set([...list, offer])]));
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
      termsBox.current?.scrollIntoView({ behavior: "smooth", block: "center" });
      termsBox.current?.focus({ preventScroll: true });
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

  const headingProps = { ref: heading, tabIndex: -1, className: "text-3xl font-extrabold tracking-tight outline-none sm:text-4xl lg:short:text-3xl" };
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
            className={`flex w-fit items-center gap-1.5 text-sm font-semibold underline-offset-4 hover:text-foreground ${
              declined.includes(offer) ? "text-foreground" : "text-muted underline"
            }`}
          >
            {declined.includes(offer) && <Check aria-hidden="true" className="size-4 text-success" />}
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
    <div className="mx-auto grid w-full max-w-6xl grid-cols-1 gap-8 px-4 pb-36 pt-6 sm:px-6 lg:grid-cols-[1fr_20rem] lg:pb-16 lg:pt-8">
      <div className="flex min-w-0 flex-col gap-6 lg:short:gap-4">
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
          <p className="text-xs text-muted lg:short:hidden">
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

        <section key={step} className="enter relative flex flex-col gap-6 lg:short:gap-4">
          {content}
        </section>

        {/* Back and Continue: a floating bar at the bottom of the steps on wide screens (on phones
            they sit in the bar with the plan, so they are always within reach). */}
        <div className="sticky bottom-4 z-20 hidden items-center justify-between gap-3 rounded-2xl bg-surface/90 p-3 shadow-lg ring-1 ring-border backdrop-blur lg:flex">
          {backButton ?? <span />}
          {stepIndex > 0 && step !== "summary" && (
            <p className="hidden text-sm text-muted xl:block">{t("progress.step", { step: stepIndex + 1, total: steps.length })}</p>
          )}
          {forwardButton}
        </div>
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
              className="font-semibold text-primary underline-offset-4 hover:underline"
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
    </div>
  );
}
