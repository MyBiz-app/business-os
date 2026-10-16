/** A network's mark: its brand color with a simple glyph. Decorative (the name is always shown).
 * `muted` greys it for a network that cannot be connected yet. */
const TILES: Record<string, { bg: string; glyph?: string }> = {
  facebook: { bg: "#1877F2", glyph: "f" },
  instagram: { bg: "linear-gradient(135deg,#F58529,#DD2A7B 55%,#8134AF)" },
  threads: { bg: "#111111", glyph: "@" },
  youtube: { bg: "#FF0000" },
  tiktok: { bg: "#111111", glyph: "♪" },
  google_business: { bg: "#4285F4", glyph: "G" },
  x: { bg: "#111111", glyph: "X" },
  linkedin: { bg: "#0A66C2", glyph: "in" },
  pinterest: { bg: "#E60023", glyph: "P" },
  snapchat: { bg: "#FFFC00", glyph: "S" },
};

export function NetworkIcon({ network, muted = false, size = "md" }: { network: string; muted?: boolean; size?: "sm" | "md" }) {
  const tile = TILES[network] ?? { bg: "#64748B", glyph: network.slice(0, 1).toUpperCase() };
  const box = size === "sm" ? "size-8 rounded-lg text-sm" : "size-12 rounded-2xl text-xl";
  return (
    <span
      aria-hidden="true"
      style={{ background: tile.bg }}
      className={`inline-flex shrink-0 items-center justify-center font-extrabold ${network === "snapchat" ? "text-black" : "text-white"} ${box} ${muted ? "opacity-40 grayscale" : ""}`}
    >
      {network === "instagram" ? (
        <svg viewBox="0 0 24 24" className="size-3/5" fill="none" stroke="currentColor" strokeWidth="2">
          <rect x="3.5" y="3.5" width="17" height="17" rx="5" />
          <circle cx="12" cy="12" r="4" />
          <circle cx="17.2" cy="6.8" r="0.8" fill="currentColor" stroke="none" />
        </svg>
      ) : network === "youtube" ? (
        <svg viewBox="0 0 24 24" className="size-3/5" fill="currentColor">
          <path d="M9 7.5v9l7.5-4.5z" />
        </svg>
      ) : (
        tile.glyph
      )}
    </span>
  );
}
