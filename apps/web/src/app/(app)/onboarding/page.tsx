import { getTranslations } from "next-intl/server";

import { getApi, unwrap } from "@/lib/api";

import { OnboardingForm } from "./onboarding-form";

export default async function OnboardingPage() {
  const t = await getTranslations("onboarding");
  const timeZones = Intl.supportedValuesOf("timeZone");
  const api = await getApi();
  const catalogs = Object.fromEntries(
    await Promise.all(
      (["ILS", "USD", "EUR"] as const).map(async (currency) => [
        currency,
        unwrap(await api.GET("/modules/catalog", { params: { query: { currency } } })),
      ]),
    ),
  );

  return (
    <main className="enter flex flex-1 items-start justify-center px-4 py-12">
      <div className="flex w-full max-w-xl flex-col gap-6 card p-6 sm:p-8">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-bold">{t("title")}</h1>
          <p className="text-sm text-muted">{t("subtitle")}</p>
        </div>
        <OnboardingForm timeZones={timeZones} catalogs={catalogs} />
      </div>
    </main>
  );
}
