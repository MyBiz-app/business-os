import type { ComponentType, ReactNode } from "react";
import { Suspense } from "react";

import { isSolo, visibleTopics } from "@/lib/solo";
import { getTenant } from "@/lib/tenant";

import AiConnectionsPage from "./ai-connections/page";
import BookingSettingsPage from "./bookings/page";
import BrandingSettingsPage from "./branding/page";
import BusinessSettingsPage from "./business/page";
import DataSettingsPage from "./data/page";
import HelpSettingsPage from "./help/page";
import IntegrationsPage from "./integrations/page";
import MembershipSettingsPage from "./memberships/page";
import ModulesPage from "./modules/page";
import TermsSettingsPage from "./terms/page";
import type { INLINE_TOPICS } from "./settings-room";
import { topicsFor, type TopicKey } from "./topics";

const PAGES: Record<(typeof INLINE_TOPICS)[number], ComponentType> = {
  business: BusinessSettingsPage,
  memberships: MembershipSettingsPage,
  bookings: BookingSettingsPage,
  terms: TermsSettingsPage,
  branding: BrandingSettingsPage,
  modules: ModulesPage,
  integrations: IntegrationsPage,
  aiConnections: AiConnectionsPage,
  data: DataSettingsPage,
  help: HelpSettingsPage,
};

function inlineOnly(key: TopicKey): key is keyof typeof PAGES {
  return key in PAGES;
}

/** `/settings`: every topic as a section of one page; the room's menu scrolls to them. Billing and
 * the audit log keep their own pages (they have sub-pages and paging). The topic pages stay
 * reachable at their own addresses too. */
export default async function SettingsIndexPage(): Promise<ReactNode> {
  const { tenant } = await getTenant();
  const keys = visibleTopics(topicsFor(tenant.role), isSolo(tenant)).map((topic) => topic.key).filter(inlineOnly);

  return (
    <div className="flex flex-col gap-10">
      {keys.map((key, index) => {
        const Topic = PAGES[key];
        return (
          <section key={key} id={key} data-settings-topic={key} className={`scroll-anchor ${index > 0 ? "border-t border-border pt-10" : ""}`}>
            <Suspense fallback={<div aria-hidden="true" className="h-40 animate-pulse rounded-2xl bg-foreground/5" />}>
              <Topic />
            </Suspense>
          </section>
        );
      })}
    </div>
  );
}
