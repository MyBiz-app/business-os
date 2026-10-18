"use client";

import { categories, childrenOf, isOpen } from "@business-os/verticals";
import { ArrowRight } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useId, useState, useTransition } from "react";

import { Container } from "@/components/layout/container";
import { formatMoney } from "@/lib/money";
import { type Currency, encodePlan, type SignupPlan, type SiteFee } from "@/lib/signup-plan";
import { industryTexts } from "@/lib/verticals";

import { accountExists } from "./actions";

type Props = { currency: Currency; signedIn: boolean; price?: SiteFee };

/** "Website only" from the landing page: first "do you already have an account?", so nobody opens
 * a second business; otherwise a short sign-up (name, email, kind of business) that opens a
 * business on the website-only track and goes straight to the website brief. */
export function SiteOnlyStart({ currency, signedIn, price }: Props) {
  const t = useTranslations("start.siteOnly");
  const { text } = industryTexts(useTranslations());
  const locale = useLocale();
  const router = useRouter();
  const nameId = useId();
  const kindId = useId();
  const emailId = useId();
  const [fresh, setFresh] = useState(false);
  const [name, setName] = useState("");
  const [kind, setKind] = useState("");
  const [email, setEmail] = useState("");
  const [existing, setExisting] = useState(false);
  const [touched, setTouched] = useState(false);
  const [pending, start] = useTransition();
  const money = (amount: number) => formatMoney(amount, currency, locale);
  const emailOk = signedIn || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
  const valid = name.trim().length > 0 && isOpen(kind) && emailOk;
  const login = `/login?next=${encodeURIComponent("/website")}`;

  const submit = () => {
    setTouched(true);
    if (!valid) return;
    start(async () => {
      if (!signedIn && (await accountExists(email)) === true) {
        setExisting(true);
        return;
      }
      const plan: SignupPlan = { vertical: kind, name: name.trim(), clients: 0, staff: 1, locations: 1, currency, modules: {}, site: "build", track: "website_only" };
      const target = `/start/finish?p=${encodePlan(plan)}`;
      router.push(signedIn ? target : `/signup?email=${encodeURIComponent(email.trim())}&next=${encodeURIComponent(target)}`);
    });
  };

  const options = categories().flatMap((category) => {
    const kinds = childrenOf(category.key).filter((child) => isOpen(child.key));
    if (kinds.length === 0) return isOpen(category.key) ? [<option key={category.key} value={category.key}>{text(category.key, "name")}</option>] : [];
    return [
      <optgroup key={category.key} label={text(category.key, "name")}>
        {kinds.map((child) => (
          <option key={child.key} value={child.key}>
            {text(child.key, "name")}
          </option>
        ))}
      </optgroup>,
    ];
  });

  return (
    <Container size="prose" className="enter flex flex-col gap-8 py-10 sm:py-14">
      <div className="flex flex-col gap-2">
        <p className="text-sm font-semibold text-primary-ink">{t("eyebrow")}</p>
        <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl">{t("title")}</h1>
        <p className="text-base text-muted sm:text-lg">{t("subtitle")}</p>
        {price && <p className="text-sm font-semibold">{t("price", { setup: money(price.setup), monthly: money(price.monthly) })}</p>}
      </div>

      {!fresh ? (
        <section aria-labelledby="site-account" className="flex flex-col gap-4">
          <h2 id="site-account" className="text-xl font-bold">
            {t("account.question")}
          </h2>
          <div className="grid gap-3 sm:grid-cols-2">
            <Link href={signedIn ? "/website" : login} className="card flex flex-col gap-1 p-5 hover:border-primary/50">
              <span className="font-bold">{signedIn ? t("account.yesSignedIn") : t("account.yes")}</span>
              <span className="text-sm text-muted">{t("account.yesText")}</span>
            </Link>
            <button type="button" onClick={() => setFresh(true)} className="btn-plain card flex flex-col gap-1 p-5 text-start hover:border-primary/50">
              <span className="font-bold">{signedIn ? t("account.noSignedIn") : t("account.no")}</span>
              <span className="text-sm text-muted">{t("account.noText")}</span>
            </button>
          </div>
        </section>
      ) : (
        <form
          aria-labelledby="site-form"
          className="flex flex-col gap-5"
          onSubmit={(event) => {
            event.preventDefault();
            submit();
          }}
        >
          <h2 id="site-form" className="text-xl font-bold">
            {t("form.title")}
          </h2>
          <div className="flex flex-col gap-1.5">
            <label htmlFor={nameId} className="font-semibold">
              {t("form.name")}
            </label>
            <input id={nameId} value={name} maxLength={120} autoComplete="organization" onChange={(event) => setName(event.target.value)} aria-invalid={touched && !name.trim() ? true : undefined} className="control w-full px-4 py-3 text-lg" />
          </div>
          <div className="flex flex-col gap-1.5">
            <label htmlFor={kindId} className="font-semibold">
              {t("form.kind")}
            </label>
            <select id={kindId} value={kind} onChange={(event) => setKind(event.target.value)} aria-invalid={touched && !isOpen(kind) ? true : undefined} className="control w-full px-4 py-3 text-lg">
              <option value="">{t("form.kindPlaceholder")}</option>
              {options}
            </select>
          </div>
          {!signedIn && (
            <div className="flex flex-col gap-1.5">
              <label htmlFor={emailId} className="font-semibold">
                {t("form.email")}
              </label>
              <input
                id={emailId}
                type="email"
                dir="ltr"
                value={email}
                autoComplete="email"
                maxLength={254}
                onChange={(event) => {
                  setEmail(event.target.value);
                  setExisting(false);
                }}
                aria-invalid={touched && !emailOk ? true : undefined}
                className="control w-full px-4 py-3 text-lg"
              />
            </div>
          )}
          {touched && !valid && (
            <p role="alert" className="text-sm text-danger">
              {t("form.incomplete")}
            </p>
          )}
          {existing && (
            <p role="status" className="rounded-xl bg-warning/10 px-4 py-3 text-sm">
              {t("existing.text")}{" "}
              <Link href={login} className="font-semibold text-primary-ink underline-offset-4 hover:underline">
                {t("existing.cta")}
              </Link>
            </p>
          )}
          <div className="flex flex-wrap items-center gap-3">
            <button type="submit" disabled={pending} className="btn-primary px-6 py-3">
              {t("form.submit")} <ArrowRight aria-hidden="true" className="size-4 rtl:rotate-180" />
            </button>
            <button type="button" onClick={() => setFresh(false)} className="btn-link text-sm text-muted underline">
              {t("form.back")}
            </button>
          </div>
          <p className="text-xs text-muted">{t("form.note")}</p>
        </form>
      )}
    </Container>
  );
}
