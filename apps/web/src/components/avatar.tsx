/** Initials in a soft circle; the hue is derived from a stable id so a person keeps their color. */
export function Avatar({ id, name, size = "md" }: { id: string; name: string; size?: "sm" | "md" | "lg" }) {
  let hash = 0;
  for (const char of id) hash = (hash * 31 + char.charCodeAt(0)) | 0;
  const hue = Math.abs(hash) % 360;
  const initials = name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0])
    .join("");
  const sizes = { sm: "size-7 text-xs", md: "size-9 text-sm", lg: "size-14 text-xl" };
  return (
    <span
      aria-hidden="true"
      style={{ "--hue": hue } as React.CSSProperties}
      className={`inline-flex shrink-0 items-center justify-center rounded-full font-semibold ${sizes[size]} bg-[hsl(var(--hue)_70%_92%)] text-[hsl(var(--hue)_55%_28%)] dark:bg-[hsl(var(--hue)_35%_22%)] dark:text-[hsl(var(--hue)_70%_82%)]`}
    >
      {initials}
    </span>
  );
}
