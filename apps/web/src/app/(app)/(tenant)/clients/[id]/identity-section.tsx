import { getTranslations } from "next-intl/server";

import { IdentityEditor } from "@/components/identity-editor";
import { Card } from "@/components/ui/card";

/** The client's ID number, when the business asks its clients for one. */
export async function IdentitySection({ clientId }: { clientId: string }) {
  const t = await getTranslations("identity");
  return (
    <Card as="section" aria-labelledby="identity-heading" className="flex flex-col gap-3">
      <div className="flex flex-col gap-1">
        <h2 id="identity-heading" className="text-lg font-semibold">
          {t("title")}
        </h2>
        <p className="text-sm text-muted">{t("clientIntro")}</p>
      </div>
      <IdentityEditor subject={{ kind: "client", id: clientId }} />
    </Card>
  );
}
