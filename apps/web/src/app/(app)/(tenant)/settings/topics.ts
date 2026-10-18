/** The topics of the settings room, in menu order. To add a topic: add a row here, a page at its
 * `href`, and its labels under `settings.nav` in the translations. To add a field to an existing
 * topic, add it to that topic's page (for example `business/page.tsx`); the menu does not change. */
export const SETTINGS_TOPICS = [
  { key: "business", href: "/settings/business", group: "business" },
  { key: "bookings", href: "/settings/bookings", group: "business" },
  { key: "branding", href: "/settings/branding", group: "look" },
  { key: "modules", href: "/settings/modules", group: "plan" },
  { key: "billing", href: "/settings/billing", group: "plan" },
  { key: "integrations", href: "/settings/integrations", group: "connections" },
  { key: "audit", href: "/settings/audit", group: "security", roles: ["owner", "manager"] },
  { key: "data", href: "/settings/data", group: "data", roles: ["owner"] },
  { key: "help", href: "/settings/help", group: "help" },
] as const;

export type SettingsTopic = (typeof SETTINGS_TOPICS)[number];
export type TopicKey = SettingsTopic["key"];
export type TopicGroup = SettingsTopic["group"];

/** The topics a role may open. */
export function topicsFor(role: string): SettingsTopic[] {
  return SETTINGS_TOPICS.filter((topic) => !("roles" in topic) || (topic.roles as readonly string[]).includes(role));
}
