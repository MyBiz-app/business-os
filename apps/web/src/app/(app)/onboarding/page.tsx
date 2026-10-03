import { getTranslations } from "next-intl/server";

import { OnboardingForm } from "./onboarding-form";

export default async function OnboardingPage() {
  const t = await getTranslations("onboarding");
  const timeZones = Intl.supportedValuesOf("timeZone");

  return (
    <main className="flex flex-1 items-start justify-center px-4 py-12">
      <div className="flex w-full max-w-md flex-col gap-6 rounded-2xl border border-border bg-surface p-6 sm:p-8">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-bold">{t("title")}</h1>
          <p className="text-sm text-muted">{t("subtitle")}</p>
        </div>
        <OnboardingForm timeZones={timeZones} />
      </div>
    </main>
  );
}
