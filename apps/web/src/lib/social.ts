/** The company's social profiles, shown in the marketing footer. A link appears only once its
 * `NEXT_PUBLIC_SOCIAL_*` environment variable holds the profile URL, so nothing points nowhere. */
const SOCIAL = [
  { key: "linkedin", label: "LinkedIn", url: process.env.NEXT_PUBLIC_SOCIAL_LINKEDIN },
  { key: "facebook", label: "Facebook", url: process.env.NEXT_PUBLIC_SOCIAL_FACEBOOK },
  { key: "instagram", label: "Instagram", url: process.env.NEXT_PUBLIC_SOCIAL_INSTAGRAM },
  { key: "youtube", label: "YouTube", url: process.env.NEXT_PUBLIC_SOCIAL_YOUTUBE },
  { key: "x", label: "X", url: process.env.NEXT_PUBLIC_SOCIAL_X },
] as const;

export function socialLinks(): { key: string; label: string; url: string }[] {
  return SOCIAL.flatMap(({ key, label, url }) => (url?.startsWith("https://") ? [{ key, label, url }] : []));
}
