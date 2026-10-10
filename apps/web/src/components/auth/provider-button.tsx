import { getTranslations } from "next-intl/server";

import { oauthSignIn } from "@/app/(auth)/actions";
import type { ProviderButton as Button } from "@/lib/auth-providers";

import { PROVIDER_MARKS } from "./provider-marks";

/** One "Continue with ..." button; a provider that is not live yet is disabled and says so. */
export async function ProviderButton({ provider, live, next, large }: Button & { next?: string; large?: boolean }) {
  const t = await getTranslations("auth.oauth");
  const Mark = PROVIDER_MARKS[provider];
  const size = large ? "px-4 py-3 text-base" : "px-4 py-2.5";
  if (!live) {
    return (
      <button type="button" disabled aria-disabled="true" className={`btn-secondary flex w-full items-center justify-center gap-3 opacity-60 ${size}`}>
        <Mark />
        {t(provider)}
        <span className="rounded-full border border-border px-2 py-0.5 text-xs font-medium text-muted">{t("soon")}</span>
      </button>
    );
  }
  return (
    <form action={oauthSignIn}>
      <input type="hidden" name="provider" value={provider} />
      {next && <input type="hidden" name="next" value={next} />}
      <button type="submit" className={`btn-secondary flex w-full items-center justify-center gap-3 ${size}`}>
        <Mark />
        {t(provider)}
      </button>
    </form>
  );
}
