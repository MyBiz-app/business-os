import { ScopedMessages } from "@/components/scoped-messages";
import { AccessibilityWidget } from "@/components/accessibility-widget";
import { MarketingHeader } from "@/components/marketing/marketing-header";
import { SignedOutNotice } from "@/components/marketing/signed-out-notice";

/** The public marketing site: about MyBiz, for businesses considering it. */
export default function MarketingLayout({ children }: LayoutProps<"/">) {
  return (
    <ScopedMessages scopes={["marketing"]}>
    <div className="mk flex flex-1 flex-col">
      <SignedOutNotice />
      <MarketingHeader />
      <div className="flex flex-1 flex-col">{children}</div>
      <AccessibilityWidget />
    </div>
    </ScopedMessages>
  );
}
