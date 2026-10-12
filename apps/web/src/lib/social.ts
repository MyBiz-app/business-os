/** The company's social profiles, shown in the marketing footer. Each falls back to a placeholder
 * profile URL until the real page exists; set `NEXT_PUBLIC_SOCIAL_*` to the real URL to replace it. */
const SOCIAL = [
  { key: "linkedin", label: "LinkedIn", url: process.env.NEXT_PUBLIC_SOCIAL_LINKEDIN || "https://www.linkedin.com/company/mybiz" },
  { key: "facebook", label: "Facebook", url: process.env.NEXT_PUBLIC_SOCIAL_FACEBOOK || "https://www.facebook.com/mybiz" },
  { key: "instagram", label: "Instagram", url: process.env.NEXT_PUBLIC_SOCIAL_INSTAGRAM || "https://www.instagram.com/mybiz" },
  { key: "youtube", label: "YouTube", url: process.env.NEXT_PUBLIC_SOCIAL_YOUTUBE || "https://www.youtube.com/@mybiz" },
  { key: "x", label: "X", url: process.env.NEXT_PUBLIC_SOCIAL_X || "https://x.com/mybiz" },
] as const;

export function socialLinks(): { key: string; label: string; url: string }[] {
  return SOCIAL.flatMap(({ key, label, url }) => (url?.startsWith("https://") ? [{ key, label, url }] : []));
}
