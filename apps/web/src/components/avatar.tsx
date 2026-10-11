/* eslint-disable @next/next/no-img-element -- pictures come from our own private route */

/** Where the web app serves a person's picture (signed in, scoped to the current business),
 * from the API's `avatar_url` (its `?v=` version lets the browser keep it). */
export function avatarSrc(userId: string, apiPath: string | null | undefined): string | null {
  if (!apiPath) return null;
  const version = apiPath.split("?v=")[1] ?? "";
  return `/avatars/${userId}?v=${version}`;
}

const SIZES = { xs: "size-6 text-[0.625rem]", sm: "size-7 text-xs", md: "size-9 text-sm", lg: "size-14 text-xl", xl: "size-24 text-3xl" };

/** A person's picture in a circle, or their initials in a soft circle whose hue comes from a
 * stable id, so a person keeps their color. */
export function Avatar({
  id,
  name,
  size = "md",
  src = null,
  className = "",
}: {
  id: string;
  name: string;
  size?: keyof typeof SIZES;
  src?: string | null;
  className?: string;
}) {
  if (src) {
    return (
      <img
        src={src}
        alt=""
        aria-hidden="true"
        loading="lazy"
        decoding="async"
        className={`inline-block shrink-0 rounded-full object-cover ring-1 ring-border ${SIZES[size]} ${className}`}
      />
    );
  }
  let hash = 0;
  for (const char of id) hash = (hash * 31 + char.charCodeAt(0)) | 0;
  const hue = Math.abs(hash) % 360;
  const initials = name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0])
    .join("");
  return (
    <span
      aria-hidden="true"
      style={{ "--hue": hue } as React.CSSProperties}
      className={`inline-flex shrink-0 items-center justify-center rounded-full font-semibold ${SIZES[size]} bg-[hsl(var(--hue)_70%_92%)] text-[hsl(var(--hue)_55%_28%)] dark:bg-[hsl(var(--hue)_35%_22%)] dark:text-[hsl(var(--hue)_70%_82%)] ${className}`}
    >
      {initials}
    </span>
  );
}
