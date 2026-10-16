import { getTranslations } from "next-intl/server";

import { SubmitButton } from "@/components/form/submit-button";
import { unwrap } from "@/lib/api";
import { getTenant } from "@/lib/tenant";

import { selectAccounts } from "./actions";
import { NetworkIcon } from "./network-icon";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const ERRORS = ["state", "denied", "network", "empty"] as const;

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

/** What a network's page sent the owner back with: a result message, or the accounts to choose from. */
export async function ConnectNotice({ query, canManage }: { query: Record<string, string | string[] | undefined>; canManage: boolean }) {
  const t = await getTranslations("content.connect");
  const error = ERRORS.find((e) => e === first(query.connect_error));
  if (error) {
    return (
      <p role="alert" className="rounded-xl border border-danger/40 bg-danger/10 px-4 py-3 text-sm font-medium">
        {t(`error.${error}` as "error.state")}
      </p>
    );
  }
  if (first(query.connected) === "1") {
    return (
      <p role="status" className="rounded-xl border border-success/40 bg-success/10 px-4 py-3 text-sm font-medium">
        {t("done")}
      </p>
    );
  }
  const pending = first(query.connect);
  if (!pending || !UUID.test(pending) || !canManage) return null;
  const { api, scope } = await getTenant();
  const result = await api.GET("/social/pending/{pending_id}", { params: { ...scope, path: { pending_id: pending } } });
  if (!result.response.ok) {
    return (
      <p role="alert" className="rounded-xl border border-danger/40 bg-danger/10 px-4 py-3 text-sm font-medium">
        {t("error.expired")}
      </p>
    );
  }
  const { candidates } = unwrap(result);
  return (
    <form action={selectAccounts.bind(null, pending)} className="card flex flex-col gap-4 p-5">
      <fieldset className="flex flex-col gap-3">
        <legend className="text-lg font-bold">{t("choose.title")}</legend>
        <p className="text-sm text-muted">{t("choose.text")}</p>
        {candidates.map((c) => (
          <label key={c.external_id} className="flex items-center gap-3">
            <input type="checkbox" name="external_id" value={c.external_id} defaultChecked className="size-4" />
            <NetworkIcon network={c.network} />
            <span className="font-semibold">{c.name}</span>
            <span className="text-sm text-muted">{t(`choose.network.${c.network}` as "choose.network.facebook")}</span>
          </label>
        ))}
      </fieldset>
      <div>
        <SubmitButton className="px-4 py-2">{t("choose.submit")}</SubmitButton>
      </div>
    </form>
  );
}
