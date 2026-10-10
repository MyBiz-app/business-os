import { getTranslations } from "next-intl/server";

import { providerButtons } from "@/lib/auth-providers";

import { ProviderButton } from "./provider-button";

/** "Continue with Google / Apple", above the email form; nothing when no button applies. */
export async function OAuthButtons({ next }: { next?: string }) {
  const providers = await providerButtons();
  if (providers.length === 0) return null;
  const t = await getTranslations("auth.oauth");
  return (
    <div className="flex flex-col gap-3">
      {providers.map((button) => (
        <ProviderButton key={button.provider} {...button} next={next} />
      ))}
      <p className="flex items-center gap-3 text-xs text-muted before:h-px before:flex-1 before:bg-border after:h-px after:flex-1 after:bg-border">
        {t("or")}
      </p>
    </div>
  );
}
