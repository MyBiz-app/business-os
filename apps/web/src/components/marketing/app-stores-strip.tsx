import { BRAND } from "@business-os/i18n/brand";
import { getTranslations } from "next-intl/server";

import { Container } from "@/components/layout/container";

/** Until the apps are published in the stores, both badges say "coming soon" and open the web app. */
const WEB_APP_URL = process.env.NEXT_PUBLIC_CLIENT_APP_URL || BRAND.appUrl;

function PlayGlyph() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" focusable="false" className="size-6">
      <path d="M4 3.2v17.6a1 1 0 0 0 1.5.86l14.6-8.8a1 1 0 0 0 0-1.72L5.5 2.34A1 1 0 0 0 4 3.2Z" />
    </svg>
  );
}

function AppleGlyph() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" focusable="false" className="size-6">
      <path d="M16.4 12.6c0-2.4 2-3.5 2.1-3.6-1.1-1.7-2.9-1.9-3.5-1.9-1.5-.15-2.9.9-3.7.9s-1.9-.85-3.2-.8c-1.6 0-3.1 1-4 2.4-1.7 3-.45 7.4 1.2 9.8.8 1.2 1.8 2.5 3.1 2.4 1.2 0 1.7-.8 3.2-.8s1.9.8 3.2.8 2.2-1.2 3-2.4c.95-1.4 1.35-2.7 1.4-2.8-.05 0-2.8-1.1-2.8-4Zm-2.4-7c.65-.8 1.1-1.9 1-3-.95 0-2.1.65-2.8 1.45-.6.7-1.15 1.85-1 2.9 1.05.1 2.15-.55 2.8-1.35Z" />
    </svg>
  );
}

export async function AppStoresStrip() {
  const t = await getTranslations("marketing");
  const stores = [
    { key: "ios", glyph: <AppleGlyph />, label: t("footer.storeIos") },
    { key: "android", glyph: <PlayGlyph />, label: t("footer.storeAndroid") },
  ];
  return (
    <div className="border-t border-white/10">
      <Container className="flex flex-wrap items-center justify-between gap-4 py-6">
        <div className="flex flex-col gap-0.5">
          <h2 className="text-sm font-semibold text-white">{t("footer.appsTitle")}</h2>
          <p className="text-xs text-white/60">{t("footer.appsText")}</p>
        </div>
        <ul className="flex flex-wrap gap-3">
          {stores.map(({ key, glyph, label }) => (
            <li key={key}>
              <a
                href={WEB_APP_URL}
                target="_blank"
                rel="noopener noreferrer"
                aria-label={`${label}: ${t("footer.comingSoon")}`}
                className="flex items-center gap-3 rounded-xl border border-white/20 bg-white/5 px-4 py-2 text-white transition-colors hover:border-electric hover:bg-white/10"
              >
                {glyph}
                <span className="flex flex-col text-start leading-tight">
                  <span className="text-[10px] uppercase tracking-wide text-white/60">{t("footer.comingSoon")}</span>
                  <span className="text-sm font-semibold">{label}</span>
                </span>
              </a>
            </li>
          ))}
        </ul>
      </Container>
    </div>
  );
}
