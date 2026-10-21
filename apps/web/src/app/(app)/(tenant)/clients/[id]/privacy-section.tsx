"use client";

import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { CheckboxField } from "@/components/form/field";
import { FormError } from "@/components/form/form-message";

import { eraseClient, type EraseState } from "./privacy-actions";
import { CollapsibleSection } from "@/components/ui/collapsible-section";
import { Card } from "@/components/ui/card";
import { Button, ButtonLink } from "@/components/ui/button";

/** Privacy requests (owners): download the client's data, or erase their personal details. */
export function PrivacySection({ clientId, name }: { clientId: string; name: string }) {
  const t = useTranslations("privacy");
  const [state, action, pending] = useActionState<EraseState, FormData>(eraseClient.bind(null, clientId), {});

  return (
    <Card as="section" aria-labelledby="privacy-heading" className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <h2 id="privacy-heading" className="text-lg font-semibold">
          {t("title")}
        </h2>
        <p className="text-sm text-muted">{t("intro")}</p>
      </div>
      <div>
        <ButtonLink href={`/clients/${clientId}/export`} download variant="secondary">
          {t("export")}
        </ButtonLink>
      </div>
      <CollapsibleSection variant="inline" className="border-t border-border pt-4" triggerClassName="font-semibold text-danger" title={t("erase")}>
        <form action={action} className="flex flex-col gap-3">
          <p className="text-sm">{t("eraseExplain")}</p>
          <FormError message={state.error && t(`errors.${state.error}`)} />
          <CheckboxField label={t("eraseConfirm", { name })} name="confirm" />
          <div>
            <Button type="submit" variant="danger" pending={pending}>
              {t("eraseButton")}
            </Button>
          </div>
        </form>
      </CollapsibleSection>
    </Card>
  );
}
