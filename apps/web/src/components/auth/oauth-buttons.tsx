import { getTranslations } from "next-intl/server";

import { oauthSignIn } from "@/app/(auth)/actions";
import { enabledProviders } from "@/lib/auth-providers";

import { PROVIDER_MARKS } from "./provider-marks";

/** "Continue with Google / Apple", above the email form; nothing when no provider is set up. */
export async function OAuthButtons({ next }: { next?: string }) {
  const providers = await enabledProviders();
  if (providers.length === 0) return null;
  const t = await getTranslations("auth.oauth");
  return (
    <div className="flex flex-col gap-3">
      {providers.map((provider) => {
        const Mark = PROVIDER_MARKS[provider];
        return (
          <form key={provider} action={oauthSignIn}>
            <input type="hidden" name="provider" value={provider} />
            {next && <input type="hidden" name="next" value={next} />}
            <button type="submit" className="btn-secondary flex w-full items-center justify-center gap-3 px-4 py-2.5">
              <Mark />
              {t(provider)}
            </button>
          </form>
        );
      })}
      <p className="flex items-center gap-3 text-xs text-muted before:h-px before:flex-1 before:bg-border after:h-px after:flex-1 after:bg-border">
        {t("or")}
      </p>
    </div>
  );
}
