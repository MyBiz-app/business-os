import { Lock } from "lucide-react";
import { getTranslations } from "next-intl/server";
import type { components } from "@business-os/api-client";

import { SubmitButton } from "@/components/form/submit-button";

import { connectDemo, startConnect } from "./actions";
import { NetworkIcon } from "./network-icon";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

type Option = components["schemas"]["NetworkOption"];

/** Every network as a card: connect it, or "coming soon" when its connector is not ready. */
export async function ConnectCards({ networks, canManage, withDemo }: { networks: Option[]; canManage: boolean; withDemo: boolean }) {
  const t = await getTranslations("content");
  return (
    <section aria-labelledby="connect-title" className="flex flex-col gap-5">
      <div className="flex flex-col gap-1">
        <h2 id="connect-title" className="text-xl font-bold">
          {t("connect.title")}
        </h2>
        <p className="max-w-[44rem] text-muted">{t("connect.text")}</p>
      </div>
      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {networks.map((network) => {
          const soon = network.status === "soon";
          return (
            <Card as="li" key={network.network} className="flex flex-col gap-3">
              <div className="flex items-center gap-3">
                <NetworkIcon network={network.network} muted={soon} />
                <div className="min-w-0 flex-1">
                  <h3 className="truncate font-bold">{t(`networks.${network.network}` as "networks.facebook")}</h3>
                  {network.connected > 0 && <p className="text-sm text-muted">{t("connect.connected", { count: network.connected })}</p>}
                </div>
                {soon && (
                  <Badge>{t("connect.soon")}</Badge>
                )}
              </div>
              <p className="flex-1 text-sm text-muted">{network.gives.map((key) => t(`gives.${key}` as "gives.followers")).join(" · ")}</p>
              {soon ? (
                <Button variant="secondary" disabled className="justify-center">
                  <Lock aria-hidden="true" className="size-4" />
                  {t("connect.soon")}
                </Button>
              ) : canManage ? (
                <form action={startConnect.bind(null, network.provider)}>
                  <SubmitButton className="w-full px-4 py-2">{t("connect.button")}</SubmitButton>
                </form>
              ) : null}
            </Card>
          );
        })}
      </ul>
      {!canManage && <p role="note" className="text-sm text-muted">{t("connect.noAccess")}</p>}
      <p className="text-sm text-muted">{t("connect.privacy")}</p>
      {withDemo && canManage && (
        <form action={connectDemo} className="card flex flex-wrap items-center justify-between gap-3 p-4 sm:p-5">
          <p className="max-w-[36rem] text-sm text-muted">{t("connect.demoNote")}</p>
          <SubmitButton variant="secondary">{t("connect.demo")}</SubmitButton>
        </form>
      )}
    </section>
  );
}
