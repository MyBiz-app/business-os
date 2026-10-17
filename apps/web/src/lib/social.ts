import { BRAND } from "@business-os/i18n/brand";

/** The company's social profiles, shown in the marketing footer. The addresses come from brand.json
 * (`social`); set `NEXT_PUBLIC_SOCIAL_*` to the real URL to override one. */
const SOCIAL = [
  { key: "linkedin", label: "LinkedIn", url: process.env.NEXT_PUBLIC_SOCIAL_LINKEDIN || BRAND.social.linkedin },
  { key: "facebook", label: "Facebook", url: process.env.NEXT_PUBLIC_SOCIAL_FACEBOOK || BRAND.social.facebook },
  { key: "instagram", label: "Instagram", url: process.env.NEXT_PUBLIC_SOCIAL_INSTAGRAM || BRAND.social.instagram },
  { key: "youtube", label: "YouTube", url: process.env.NEXT_PUBLIC_SOCIAL_YOUTUBE || BRAND.social.youtube },
  { key: "x", label: "X", url: process.env.NEXT_PUBLIC_SOCIAL_X || BRAND.social.x },
] as const;

export function socialLinks(): { key: string; label: string; url: string }[] {
  return SOCIAL.flatMap(({ key, label, url }) => (url?.startsWith("https://") ? [{ key, label, url }] : []));
}
