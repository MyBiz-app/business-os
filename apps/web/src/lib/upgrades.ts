/** Modules that add a page to the business app. A business that doesn't have one still sees it
 * in the menu, locked, leading to a preview with "add to plan" (/upgrade/<offer>). */
export const UPGRADES = {
  client_app: { modules: ["client_app"], href: "/clients/join", permission: "clients.read" },
  ai: { modules: ["ai_basic", "ai_pro"], href: "/assistant", permission: "ai.use" },
  crm: { modules: ["crm"], href: "/leads", permission: "clients.read" },
  whatsapp: { modules: ["whatsapp"], href: "/messages", permission: "clients.read" },
} as const;

export type Upgrade = keyof typeof UPGRADES;

export function isUpgrade(value: string): value is Upgrade {
  return value in UPGRADES;
}

export function hasUpgrade(modules: readonly string[], offer: Upgrade): boolean {
  return UPGRADES[offer].modules.some((key) => modules.includes(key));
}
