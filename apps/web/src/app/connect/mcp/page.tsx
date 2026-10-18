import { Plug } from "lucide-react";
import { getTranslations } from "next-intl/server";

import { AuthHeading, AuthShell } from "@/components/auth/auth-shell";
import { SelectField } from "@/components/form/field";
import { ScopedMessages } from "@/components/scoped-messages";
import { getApi } from "@/lib/api";
import { isolate } from "@/lib/bidi";
import { getActiveMembership } from "@/lib/tenant";

import { approveConnection, denyConnection } from "./actions";

const first = (value: string | string[] | undefined) => (Array.isArray(value) ? value[0] : value) ?? "";

/** Where an AI app (Claude, ChatGPT) sends the person to let it read their business. The proxy
 * has already made them sign in; the API checks every value again when they approve. */
export default async function ConnectMcpPage({ searchParams }: PageProps<"/connect/mcp">) {
  const params = await searchParams;
  const clientId = first(params.client_id);
  const redirectUri = first(params.redirect_uri);
  const codeChallenge = first(params.code_challenge);
  const state = first(params.state);
  const t = await getTranslations("mcpConnect");

  const { data: app } =
    clientId && redirectUri && codeChallenge
      ? await (await getApi()).GET("/mcp-oauth/clients/{client_id}", {
          params: { path: { client_id: clientId }, query: { redirect_uri: redirectUri } },
        })
      : { data: undefined };
  const { me, membership } = await getActiveMembership();

  let content: React.ReactNode;
  if (!app) {
    content = <p>{t("invalid")}</p>;
  } else if (!membership) {
    content = <p>{t("noBusiness")}</p>;
  } else {
    const hidden = { client_id: clientId, redirect_uri: redirectUri, code_challenge: codeChallenge, state };
    content = (
      <>
        <p>{t("body", { app: isolate(app.client_name) })}</p>
        <ul className="list-disc ps-5 text-sm text-muted">
          {(t.raw("reads") as string[]).map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
        <p className="text-sm text-muted">{t("returns", { host: isolate(app.redirect_host) })}</p>
        <form action={approveConnection} className="flex flex-col gap-4">
          {Object.entries(hidden).map(([name, value]) => (
            <input key={name} type="hidden" name={name} value={value} />
          ))}
          <SelectField
            label={t("business")}
            name="tenant_id"
            defaultValue={membership.tenant_id}
            options={me.memberships.map((m) => ({ value: m.tenant_id, label: m.tenant_name }))}
          />
          <button type="submit" className="btn-primary px-4 py-2.5">
            {t("approve")}
          </button>
          <button type="submit" formAction={denyConnection} className="btn-secondary px-4 py-2.5">
            {t("deny")}
          </button>
        </form>
      </>
    );
  }

  return (
    <ScopedMessages scopes={["auth"]}>
      <AuthShell>
        <AuthHeading title={t("title")} icon={<Plug className="size-6" />} />
        {content}
      </AuthShell>
    </ScopedMessages>
  );
}
