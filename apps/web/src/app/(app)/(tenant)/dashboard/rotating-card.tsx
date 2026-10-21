
import { GettingStartedCard } from "@/components/getting-started";
import type { components } from "@business-os/api-client";

import { BranchMapCard } from "./branch-map-card";
import { WebsiteOfferCard } from "./website-offer-card";
import type { getTenant } from "@/lib/tenant";

type Context = Awaited<ReturnType<typeof getTenant>>;

/** The one card at the bottom of the home page. Never all three at once; what is most useful now
 * wins: finish the first steps, then the website offer, then the map of the branches. */
export async function RotatingCard({
  context,
  setup,
  welcome,
  websiteOffer,
  showMap,
}: {
  context: Pick<Context, "api" | "scope" | "tenant">;
  setup: components["schemas"]["GettingStarted"] | undefined;
  welcome: boolean;
  websiteOffer: boolean;
  showMap: boolean;
}) {
  if (setup && (welcome || setup.done < setup.total)) {
    return <GettingStartedCard setup={setup} welcome={welcome} business={context.tenant.name} />;
  }
  if (websiteOffer) return <WebsiteOfferCard />;
  if (showMap) return <BranchMapCard context={context} />;
  return null;
}
