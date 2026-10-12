import { ScopedMessages } from "@/components/scoped-messages";
import { MarketingFooter } from "@/components/marketing/marketing-footer";
import { MarketingHeader } from "@/components/marketing/marketing-header";

/** The public marketing site: about MyBiz, for businesses considering it. */
export default function MarketingLayout({ children }: LayoutProps<"/">) {
  return (
    <ScopedMessages scopes={["marketing"]}>
    <div className="flex flex-1 flex-col">
      <MarketingHeader />
      <div className="flex flex-1 flex-col">{children}</div>
      <MarketingFooter />
    </div>
    </ScopedMessages>
  );
}
