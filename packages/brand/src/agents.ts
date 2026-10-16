/**
 * The AI team's faces. The gallery for custom agents has 25 soft 3D illustrations: sixteen varied
 * faces plus the nine original default-agent illustrations (`gallery-17` to `gallery-25`). Each is a
 * parametric character drawn by `scripts/build-agents.mjs` into `agents/<key>.svg` (the fallback)
 * and `agents/<key>.webp`. The nine default agents themselves use realistic AI-generated portraits
 * (`agents/<key>.webp`, round 6 slice U2) that the script does not draw; `DEFAULT_AGENTS` keeps
 * their accent colors and the original illustrations' looks. Change a look here, then run
 * `pnpm --filter @business-os/brand build:agents`.
 */

export type HairStyle = "short" | "long" | "bun" | "curly" | "bald" | "wavy" | "cap" | "side";
export type Accessory = "none" | "glasses" | "headset" | "tie" | "scarf" | "beard" | "earrings" | "badge";

export interface AvatarSpec {
  key: string;
  /** Background disc color (the agent's accent color for the nine defaults). */
  color: string;
  skin: string;
  hair: string;
  hairStyle: HairStyle;
  outfit: string;
  accessory: Accessory;
}

const SKINS = ["#F5CBA7", "#E8B48A", "#C98B5E", "#8D5A3B", "#F1D4B8", "#A66A45"];
const [S1, S2, S3, S4, S5, S6] = SKINS;

/** The nine default agents; `color` matches the plan's table. */
export const DEFAULT_AGENTS: readonly AvatarSpec[] = [
  { key: "chief", color: "#7C3AED", skin: S2, hair: "#1F2937", hairStyle: "side", outfit: "#111827", accessory: "tie" },
  { key: "secretary", color: "#06B6D4", skin: S1, hair: "#7C2D12", hairStyle: "bun", outfit: "#0E7490", accessory: "headset" },
  { key: "marketing", color: "#EC4899", skin: S5, hair: "#B45309", hairStyle: "wavy", outfit: "#9D174D", accessory: "earrings" },
  { key: "sales", color: "#2563EB", skin: S3, hair: "#0F172A", hairStyle: "short", outfit: "#1E3A8A", accessory: "tie" },
  { key: "finance", color: "#10B981", skin: S1, hair: "#475569", hairStyle: "bald", outfit: "#065F46", accessory: "glasses" },
  { key: "team", color: "#F59E0B", skin: S6, hair: "#292524", hairStyle: "curly", outfit: "#B45309", accessory: "badge" },
  { key: "care", color: "#14B8A6", skin: S2, hair: "#3F2A1D", hairStyle: "short", outfit: "#0F766E", accessory: "headset" },
  { key: "analyst", color: "#6366F1", skin: S4, hair: "#111827", hairStyle: "cap", outfit: "#3730A3", accessory: "glasses" },
  { key: "creative", color: "#F43F5E", skin: S5, hair: "#7E22CE", hairStyle: "long", outfit: "#9F1239", accessory: "scarf" },
];

const BG = ["#7C3AED", "#2563EB", "#06B6D4", "#10B981", "#F59E0B", "#EC4899", "#6366F1", "#14B8A6"];
const HAIR = ["#111827", "#3F2A1D", "#7C2D12", "#B45309", "#475569", "#7E22CE"];
const HAIR_STYLES: HairStyle[] = ["short", "long", "bun", "curly", "bald", "wavy", "cap", "side"];
const ACCESSORIES: Accessory[] = ["none", "glasses", "headset", "tie", "scarf", "beard", "earrings", "badge"];
const OUTFIT = ["#111827", "#1E3A8A", "#0F766E", "#9D174D", "#B45309", "#3730A3", "#065F46", "#6D28D9"];

/** Sixteen gallery faces for custom agents: varied on every axis, deterministic. */
export const GALLERY_AVATARS: readonly AvatarSpec[] = Array.from({ length: 16 }, (_, i) => ({
  key: `gallery-${String(i + 1).padStart(2, "0")}`,
  color: BG[(i * 3) % BG.length],
  skin: SKINS[(i * 5 + 1) % SKINS.length],
  hair: HAIR[(i * 7) % HAIR.length],
  hairStyle: HAIR_STYLES[(i * 3 + 1) % HAIR_STYLES.length],
  outfit: OUTFIT[(i * 5) % OUTFIT.length],
  accessory: ACCESSORIES[(i * 5 + 2) % ACCESSORIES.length],
}));

/** The original nine illustrations, kept in the gallery as `gallery-17` to `gallery-25`. */
export const ILLUSTRATED_DEFAULTS: readonly AvatarSpec[] = DEFAULT_AGENTS.map((a, i) => ({ ...a, key: `gallery-${17 + i}` }));

/** Every drawn avatar (the 25 gallery faces); the nine default portraits are plain files. */
export const ALL_AVATARS: readonly AvatarSpec[] = [...GALLERY_AVATARS, ...ILLUSTRATED_DEFAULTS];

/** Relative path (inside `@business-os/brand`) of an avatar file; webp is primary, svg the fallback. */
export function avatarPath(key: string, format: "webp" | "svg" = "webp"): string {
  return `agents/${key}.${format}`;
}

/** Darkens or lightens a #RRGGBB color; `amount` is -1 (black) to 1 (white). */
export function shade(hex: string, amount: number): string {
  const n = parseInt(hex.slice(1), 16);
  const mix = (c: number) => Math.round(amount < 0 ? c * (1 + amount) : c + (255 - c) * amount);
  const r = mix((n >> 16) & 255), g = mix((n >> 8) & 255), b = mix(n & 255);
  return `#${((1 << 24) | (r << 16) | (g << 8) | b).toString(16).slice(1).toUpperCase()}`;
}

/** The avatar as a 256 x 256 SVG: a soft-lit disc, shoulders, head, hair and one accessory. */
export function avatarSvg(a: AvatarSpec): string {
  const id = a.key;
  const skinD = shade(a.skin, -0.18), skinL = shade(a.skin, 0.25);
  const hairD = shade(a.hair, -0.35), hairL = shade(a.hair, 0.3);
  const outD = shade(a.outfit, -0.3), outL = shade(a.outfit, 0.25);
  const defs =
    `<radialGradient id="bg${id}" cx="35%" cy="25%" r="85%"><stop offset="0" stop-color="${shade(a.color, 0.35)}"/><stop offset="1" stop-color="${shade(a.color, -0.25)}"/></radialGradient>` +
    `<radialGradient id="sk${id}" cx="38%" cy="30%" r="75%"><stop offset="0" stop-color="${skinL}"/><stop offset="0.55" stop-color="${a.skin}"/><stop offset="1" stop-color="${skinD}"/></radialGradient>` +
    `<radialGradient id="hr${id}" cx="35%" cy="20%" r="85%"><stop offset="0" stop-color="${hairL}"/><stop offset="0.5" stop-color="${a.hair}"/><stop offset="1" stop-color="${hairD}"/></radialGradient>` +
    `<linearGradient id="ou${id}" x1="0" y1="0" x2="0.4" y2="1"><stop offset="0" stop-color="${outL}"/><stop offset="0.5" stop-color="${a.outfit}"/><stop offset="1" stop-color="${outD}"/></linearGradient>` +
    `<clipPath id="cl${id}"><circle cx="128" cy="128" r="128"/></clipPath>`;

  const body =
    // shoulders
    `<path d="M26 256C26 196 70 176 128 176s102 20 102 80Z" fill="url(#ou${id})"/>` +
    `<path d="M128 176c-18 0-34 4-46 10 10 18 28 28 46 28s36-10 46-28c-12-6-28-10-46-10Z" fill="${outD}" opacity=".35"/>` +
    // neck
    `<path d="M108 150h40v34c0 14-9 22-20 22s-20-8-20-22Z" fill="${skinD}"/>` +
    `<path d="M108 168c12 8 28 8 40 0v-10c-12 8-28 8-40 0Z" fill="#000" opacity=".12"/>`;

  const hairBack =
    a.hairStyle === "long"
      ? `<path d="M76 104c-6 56-4 84 8 98 14 10 74 10 88 0 12-14 14-42 8-98Z" fill="url(#hr${id})"/>`
      : a.hairStyle === "bun"
        ? `<circle cx="128" cy="40" r="22" fill="url(#hr${id})"/>`
        : a.hairStyle === "curly"
          ? [[72, 98], [64, 120], [76, 142], [184, 98], [192, 120], [180, 142], [88, 62], [128, 52], [168, 62]]
              .map(([x, y]) => `<circle cx="${x}" cy="${y}" r="22" fill="url(#hr${id})"/>`).join("")
          : a.hairStyle === "wavy"
            ? `<path d="M74 100c-12 40-6 70 8 84 8-16 12-30 14-44ZM182 100c12 40 6 70-8 84-8-16-12-30-14-44Z" fill="url(#hr${id})"/>`
            : "";

  const head =
    `<ellipse cx="73" cy="116" rx="9" ry="14" fill="${skinD}"/><ellipse cx="183" cy="116" rx="9" ry="14" fill="${skinD}"/>` +
    `<ellipse cx="128" cy="112" rx="55" ry="62" fill="url(#sk${id})"/>`;

  const beard = a.accessory === "beard"
    ? `<path d="M76 118c0 46 22 62 52 62s52-16 52-62c-10 20-26 28-52 28s-42-8-52-28Z" fill="url(#hr${id})"/>`
    : "";

  const face =
    `<ellipse cx="106" cy="118" rx="6.5" ry="8" fill="#1F2937"/><ellipse cx="150" cy="118" rx="6.5" ry="8" fill="#1F2937"/>` +
    `<circle cx="108.5" cy="115" r="2.4" fill="#fff"/><circle cx="152.5" cy="115" r="2.4" fill="#fff"/>` +
    `<path d="M98 102q8-6 16-1M142 101q8-5 16 1" stroke="${hairD}" stroke-width="3.5" stroke-linecap="round" fill="none"/>` +
    `<path d="M122 126q6 6 12 0" stroke="${skinD}" stroke-width="3" stroke-linecap="round" fill="none"/>` +
    `<path d="M112 142q16 14 32 0" stroke="${a.accessory === "beard" ? "#fff" : "#9F3B3B"}" stroke-width="4" stroke-linecap="round" fill="none"/>` +
    `<ellipse cx="92" cy="136" rx="9" ry="6" fill="#F43F5E" opacity=".16"/><ellipse cx="164" cy="136" rx="9" ry="6" fill="#F43F5E" opacity=".16"/>`;

  const hairFront =
    a.hairStyle === "short"
      ? `<path d="M72 108c-6-46 22-72 56-72s62 26 56 72c-8-22-22-34-30-36-22 8-54 8-82 36Z" fill="url(#hr${id})"/>`
      : a.hairStyle === "side"
        ? `<path d="M72 108c-8-50 22-74 58-72 36 2 60 28 54 72-6-18-14-28-26-34-28 12-56 10-86 34Z" fill="url(#hr${id})"/><path d="M96 66c20 8 44 8 62-6" stroke="${hairL}" stroke-width="3" fill="none" opacity=".5" stroke-linecap="round"/>`
        : a.hairStyle === "long" || a.hairStyle === "wavy"
          ? `<path d="M70 112c-6-52 24-78 58-78s64 26 58 78c-4-26-16-40-32-46-26 14-58 12-84 46Z" fill="url(#hr${id})"/>`
          : a.hairStyle === "bun"
            ? `<path d="M72 108c-6-46 22-70 56-70s62 24 56 70c-8-24-22-36-30-38-22 8-54 8-82 38Z" fill="url(#hr${id})"/>`
            : a.hairStyle === "curly"
              ? [[92, 66], [114, 56], [142, 56], [164, 66], [78, 84], [178, 84]]
                  .map(([x, y]) => `<circle cx="${x}" cy="${y}" r="19" fill="url(#hr${id})"/>`).join("")
              : a.hairStyle === "cap"
                ? `<g transform="translate(0 -9)"><path d="M70 98c0-40 26-62 58-62s58 22 58 62Z" fill="${a.color === "#6366F1" ? "#4338CA" : a.outfit}"/><path d="M62 98h124c6 0 10 4 10 8s-4 6-10 6H66c-6 0-8-4-8-8s2-6 4-6Z" fill="${shade(a.outfit, -0.2)}"/><path d="M92 46q36-14 72 0" stroke="#fff" stroke-width="3" opacity=".25" fill="none" stroke-linecap="round"/></g>`
                : a.hairStyle === "bald"
                  ? `<path d="M76 98c4-40 28-56 52-56s48 16 52 56c-14-14-34-20-52-20s-38 6-52 20Z" fill="${skinL}" opacity=".35"/><path d="M74 104c0 6 2 10 4 14M182 104c0 6-2 10-4 14" stroke="${a.hair}" stroke-width="7" stroke-linecap="round" fill="none"/>`
                  : "";

  const acc: Record<Accessory, string> = {
    none: "",
    beard: "",
    glasses:
      `<g fill="#fff" fill-opacity=".18" stroke="#1F2937" stroke-width="4"><rect x="86" y="104" width="38" height="28" rx="12"/><rect x="132" y="104" width="38" height="28" rx="12"/></g><path d="M124 116h8" stroke="#1F2937" stroke-width="4"/>`,
    headset:
      `<path d="M72 112c-4-48 20-72 56-72s60 24 56 72" stroke="#1F2937" stroke-width="7" fill="none" stroke-linecap="round"/><rect x="62" y="104" width="16" height="30" rx="8" fill="#1F2937"/><rect x="178" y="104" width="16" height="30" rx="8" fill="#1F2937"/><path d="M70 130c2 20 20 28 44 28" stroke="#1F2937" stroke-width="4" fill="none" stroke-linecap="round"/><circle cx="116" cy="158" r="6" fill="#1F2937"/>`,
    tie:
      `<path d="M128 178l-10 10 6 8-8 34h24l-8-34 6-8Z" fill="${a.color}"/><path d="M104 176l24 14 24-14-6-6-18 10-18-10Z" fill="#F8FAFC"/>`,
    scarf:
      `<path d="M92 170c20 14 52 14 72 0l8 18c-24 18-64 18-88 0Z" fill="${a.color}"/><path d="M146 184l14 40h-20l-6-34Z" fill="${shade(a.color, -0.2)}"/>`,
    earrings:
      `<circle cx="73" cy="134" r="5" fill="#FBBF24"/><circle cx="183" cy="134" r="5" fill="#FBBF24"/>`,
    badge:
      `<rect x="150" y="196" width="30" height="20" rx="4" fill="#F8FAFC"/><rect x="156" y="202" width="14" height="3" rx="1.5" fill="${a.color}"/><rect x="156" y="208" width="18" height="3" rx="1.5" fill="#94A3B8"/>`,
  };
  // glow behind plus a soft ground highlight keep the "3D" read
  const gloss = `<ellipse cx="96" cy="52" rx="70" ry="34" fill="#fff" opacity=".10"/>`;

  return (
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="256" height="256"><defs>${defs}</defs>` +
    `<g clip-path="url(#cl${id})"><rect width="256" height="256" fill="url(#bg${id})"/>${gloss}` +
    `${hairBack}${body}${head}${beard}${face}${hairFront}${acc[a.accessory]}</g></svg>`
  );
}
