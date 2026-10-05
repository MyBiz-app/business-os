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
import { DevSettings, I18nManager, Platform } from "react-native";
import { IntlProvider } from "use-intl";

import { loadLocale, saveLocale } from "../lib/preferences";

type LocaleContextValue = {
  locale: Locale;
  setLocale: (locale: Locale) => Promise<void>;
};

const LocaleContext = createContext<LocaleContextValue | null>(null);

function deviceLocale(): Locale {
  return matchLanguageTag(getLocales()[0]?.languageTag) ?? defaultLocale;
}

// React Native applies RTL / LTR only at startup, so a direction change needs a reload.
// On the web the document direction can simply be switched.
async function ensureDirection(locale: Locale): Promise<void> {
  const rtl = localeDirection[locale] === "rtl";
  if (Platform.OS === "web") {
    document.documentElement.dir = rtl ? "rtl" : "ltr";
    document.documentElement.lang = locale;
    return;
  }
  if (I18nManager.isRTL === rtl) return;
  I18nManager.allowRTL(rtl);
  I18nManager.forceRTL(rtl);
  // expo-updates can only reload release builds; Expo Go and dev builds use the dev reload.
  if (__DEV__) DevSettings.reload();
  else await reloadAsync();
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
