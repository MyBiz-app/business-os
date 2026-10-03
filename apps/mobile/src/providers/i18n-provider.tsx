import {
  defaultLocale,
  isLocale,
  type Locale,
  localeDirection,
  matchLanguageTag,
  messages,
} from "@business-os/i18n";
import { getLocales } from "expo-localization";
import { reloadAsync } from "expo-updates";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { I18nManager } from "react-native";
import { IntlProvider } from "use-intl";

import { loadLocale, saveLocale } from "@/lib/preferences";

type LocaleContextValue = {
  locale: Locale;
  setLocale: (locale: Locale) => Promise<void>;
};

const LocaleContext = createContext<LocaleContextValue | null>(null);

function deviceLocale(): Locale {
  return matchLanguageTag(getLocales()[0]?.languageTag) ?? defaultLocale;
}

// React Native applies RTL / LTR only at startup, so a direction change needs a reload.
async function ensureDirection(locale: Locale): Promise<void> {
  const rtl = localeDirection[locale] === "rtl";
  if (I18nManager.isRTL === rtl) return;
  I18nManager.allowRTL(rtl);
  I18nManager.forceRTL(rtl);
  await reloadAsync();
}

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale | null>(null);

  useEffect(() => {
    loadLocale().then(async (stored) => {
      const initial = isLocale(stored) ? stored : deviceLocale();
      setLocaleState(initial);
      await ensureDirection(initial);
    });
  }, []);

  const setLocale = useCallback(async (next: Locale) => {
    await saveLocale(next);
    setLocaleState(next);
    await ensureDirection(next);
  }, []);

  // Render nothing until the stored locale is known, to avoid a flash of the wrong language.
  if (!locale) return null;

  return (
    <LocaleContext.Provider value={{ locale, setLocale }}>
      <IntlProvider locale={locale} messages={messages[locale]}>
        {children}
      </IntlProvider>
    </LocaleContext.Provider>
  );
}

export function useLocaleSetting(): LocaleContextValue {
  const context = useContext(LocaleContext);
  if (!context) throw new Error("useLocaleSetting must be used inside I18nProvider");
  return context;
}
