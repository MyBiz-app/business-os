import type { Locale } from "@business-os/i18n/locales";

/** The few strings the last-resort error page needs, for both languages. It is a client bundle
 * that renders without providers, so it must not pull in the full message files; a test keeps
 * these in step with them. */
export const ERROR_MESSAGES: Record<Locale, { title: string; text: string; reference: string; retry: string; toSite: string; signOut: string }> = {
  he: {
    title: "משהו השתבש",
    text: "לא הצלחנו להציג את העמוד. נסו שוב; אם זה חוזר, פנו לתמיכה וציינו את המזהה שמופיע למטה.",
    reference: "מזהה: {code}",
    retry: "נסו שוב",
    toSite: "לאתר הציבורי",
    signOut: "התנתקות",
  },
  en: {
    title: "Something went wrong",
    text: "We couldn't show this page. Please try again; if it keeps happening, contact support and mention the reference below.",
    reference: "Reference: {code}",
    retry: "Try again",
    toSite: "Public website",
    signOut: "Sign out",
  },
};
