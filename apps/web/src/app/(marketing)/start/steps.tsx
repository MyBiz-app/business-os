"use client";

import { categories, childrenOf, vertical as findVertical } from "@business-os/verticals";
import { useTranslations } from "next-intl";
import Link from "next/link";
import type { Ref } from "react";

import { oauthSignIn } from "@/app/(auth)/actions";
import { PROVIDER_MARKS } from "@/components/auth/provider-marks";
import { VerticalIcon } from "@/components/vertical-icon";
import type { ProviderButton } from "@/lib/auth-providers";
import {
  businessNumberOk,
  CLIENT_SIZES,
  companyPrefixWarning,
  CURRENCIES,
  type Currency,
  ENTITY_TYPES,
  type EntityType,
} from "@/lib/signup-plan";
import { industryTexts } from "@/lib/verticals";

import { ChoiceGroup, StepHeading, Stepper, TextInput } from "./journey-pieces";
import type { Draft } from "./wizard-types";

/** The props the heading of every step shares (the wizard moves focus to it on each step). */
export type HeadingProps = { ref: Ref<HTMLHeadingElement>; tabIndex: number; className: string };

/** Step 1 (signed out): Google or Apple sign-in, or on with an email. */
export function AccountStep({
  providers,
  returnTo,
  headingProps,
  onEmail,
}: {
  providers: ProviderButton[];
  returnTo: string;
  headingProps: HeadingProps;
  onEmail: () => void;
}) {
  const t = useTranslations("start");
  const tAuth = useTranslations("auth.oauth");
  return (
    <>
      <StepHeading eyebrow={t("account.eyebrow")} title={<h1 {...headingProps}>{t("account.title")}</h1>} subtitle={t("account.subtitle")} />
      <div className="card flex max-w-md flex-col gap-3 p-6">
        {providers.map(({ provider, live }) => {
          const label = (
            <>
              {PROVIDER_MARKS[provider]()}
              {tAuth(provider)}
              {!live && <span className="rounded-full border border-border px-2 py-0.5 text-xs font-medium text-muted">{tAuth("soon")}</span>}
            </>
          );
          const classes = "btn-secondary flex w-full items-center justify-center gap-3 px-4 py-3 text-base";
          return live ? (
            <form key={provider} action={oauthSignIn}>
              <input type="hidden" name="provider" value={provider} />
              <input type="hidden" name="next" value={returnTo} />
              <button type="submit" className={classes}>{label}</button>
            </form>
          ) : (
            <button key={provider} type="button" disabled aria-disabled="true" className={`btn-plain ${classes} opacity-60`}>{label}</button>
          );
        })}
        <p className="flex items-center gap-3 text-xs text-muted before:h-px before:flex-1 before:bg-border after:h-px after:flex-1 after:bg-border">
          {tAuth("or")}
        </p>
        <button type="button" onClick={() => onEmail()} className="btn-primary px-4 py-3">
          {t("account.email")}
        </button>
        <p className="text-center text-sm text-muted">
          {t("account.haveAccount")}{" "}
          <Link href={`/login?next=${encodeURIComponent(returnTo)}`} className="font-semibold text-primary-ink underline-offset-4 hover:underline">
            {t("account.login")}
          </Link>
        </p>
      </div>
    </>
  );
}

/** The kind of business: a category first, then (for a category with kinds) the kind. */
/** The first question of the journey: starting from scratch, or moving a running business. */
export function PathStep({
  draft,
  headingProps,
  onChoose,
}: {
  draft: Draft;
  headingProps: HeadingProps;
  onChoose: (track: "new" | "existing") => void;
}) {
  const t = useTranslations("start.path");
  const options = ["new", "existing"] as const;
  return (
    <>
      <StepHeading eyebrow={t("eyebrow")} title={<h1 {...headingProps}>{t("title")}</h1>} subtitle={t("subtitle")} />
      <ul className="enter-items grid gap-3 sm:grid-cols-2">
        {options.map((option) => (
          <li key={option}>
            <button
              type="button"
              aria-pressed={(draft.track ?? "new") === option}
              onClick={() => onChoose(option)}
              className={`btn-plain card card-hover flex h-full w-full flex-col gap-1 p-5 text-start ${(draft.track ?? "new") === option ? "ring-2 ring-primary" : ""}`}
            >
              <span className="text-lg font-bold">{t(`${option}.title`)}</span>
              <span className="text-sm text-muted">{t(`${option}.hint`)}</span>
            </button>
          </li>
        ))}
      </ul>
    </>
  );
}

export function IndustryStep({
  draft,
  category,
  setCategory,
  headingProps,
  onChoose,
}: {
  draft: Draft;
  category: string | null;
  setCategory: (category: string | null) => void;
  headingProps: HeadingProps;
  onChoose: (vertical: string) => void;
}) {
  const t = useTranslations("start");
  const { text } = industryTexts(useTranslations());
  const choose = (vertical: string) => onChoose(vertical);
  const kinds = category ? childrenOf(category) : [];
  const card = (key: string, chosen: boolean, onClick: () => void, label: string, hint: string) => {
    const { icon, color } = findVertical(key)!;
    return (
      <button
        type="button"
        aria-pressed={chosen}
        onClick={onClick}
        className={`btn-plain card card-hover flex w-full items-center gap-4 p-5 text-start ${chosen ? "ring-2 ring-primary" : ""}`}
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
  return category ? (
    <>
      <StepHeading
        eyebrow={
          <button type="button" onClick={() => setCategory(null)} className="btn-link text-sm font-semibold text-primary-ink underline-offset-4 hover:underline">
            {t("industry.allIndustries")}
          </button>
        }
        title={<h1 {...headingProps}>{t("industry.kindTitle", { name: text(category, "name") })}</h1>}
        subtitle={t("industry.kindSubtitle")}
      />
      <ul className="enter-items grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
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
      <ul className="enter-items grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
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
        <Link href="/industries" className="font-semibold text-primary-ink underline-offset-4 hover:underline">
          {t("industry.seeAll")}
        </Link>
      </p>
    </>
  );
}

/** The business: name, legal form, size, staff, locations and currency. */
export function BusinessStep({
  draft,
  catalogCurrencies,
  update,
  numberTouched,
  setNumberTouched,
  headingProps,
  onContinue,
}: {
  draft: Draft;
  /** The currencies a price list exists for. */
  catalogCurrencies: Currency[];
  update: (changes: Partial<Draft>) => void;
  numberTouched: boolean;
  setNumberTouched: (touched: boolean) => void;
  headingProps: HeadingProps;
  onContinue: () => void;
}) {
  const t = useTranslations("start");
  const { text } = industryTexts(useTranslations());
  return (
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
          setNumberTouched(true);
          if (draft.name.trim() && businessNumberOk(draft.currency, draft.businessNumber ?? "") && (draft.currency !== "ILS" || draft.entityType)) {
            onContinue();
          }
        }}
      >
        <TextInput
          label={t("business.name")}
          value={draft.name}
          placeholder={t("business.namePlaceholder", { example: draft.vertical ? text(draft.vertical, "example") : t("business.exampleGeneric") })}
          onChange={(name) => update({ name })}
        />
        <ChoiceGroup
          legend={draft.currency === "ILS" ? t("business.entity.legend") : t("business.entity.legendOptional")}
          hint={draft.entityType ? t(`business.entity.hints.${draft.entityType}`) : t("business.entity.hint")}
          options={ENTITY_TYPES.map((value) => ({ value, label: t(`business.entity.types.${value}`) }))}
          value={draft.entityType ?? ""}
          onChange={(entityType) => update({ entityType: entityType as EntityType })}
          columns="grid-cols-2 sm:grid-cols-3"
        />
        {numberTouched && draft.currency === "ILS" && !draft.entityType && (
          <p role="alert" className="text-sm text-danger">
            {t("business.entity.required")}
          </p>
        )}
        <TextInput
          label={draft.currency === "ILS" ? t("business.number") : t("business.numberOptional")}
          value={draft.businessNumber ?? ""}
          placeholder={t("business.numberPlaceholder")}
          onChange={(businessNumber) => update({ businessNumber })}
          inputMode="numeric"
          required={draft.currency === "ILS"}
          error={numberTouched && !businessNumberOk(draft.currency, draft.businessNumber ?? "") ? t("business.numberInvalid") : undefined}
          hint={draft.currency === "ILS" ? t("business.numberHint") : undefined}
        />
        {companyPrefixWarning(draft.currency, draft.entityType, draft.businessNumber ?? "") && (
          <p role="status" className="rounded-xl bg-warning/10 px-4 py-3 text-sm">
            {t("business.entity.prefixWarning")}
          </p>
        )}
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
          options={CURRENCIES.filter((code) => catalogCurrencies.includes(code)).map((code) => ({ value: code, label: t(`business.currencies.${code}`) }))}
          value={draft.currency}
          onChange={(value) => update({ currency: value as Currency })}
          columns="grid-cols-3"
        />
      </form>
    </>
  );
}
