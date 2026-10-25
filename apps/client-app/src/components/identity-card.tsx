import { israeliIdValid, maskedId } from "@business-os/i18n/israeli-id";
import { useCallback, useMemo, useState } from "react";
import { Text } from "@business-os/app-kit/components/text";
import { useTranslations } from "use-intl";

import { SectionTitle } from "@business-os/app-kit/components/rows";
import { SegmentedControl } from "@business-os/app-kit/components/segmented-control";
import { Button, Card, ErrorText, Field, LoadError, styles } from "@business-os/app-kit/components/ui";
import { ApiError, unwrap } from "@business-os/app-kit/lib/api";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { fetchIdentity, forgetShared } from "@/lib/client-data";
import { useDataContext } from "@/lib/use-data-context";
import { useBusiness } from "@/providers/business-provider";
import { useStaff } from "@/providers/staff-provider";
import type { Palette } from "@business-os/app-kit/lib/theme";

type IdType = "il_id" | "passport" | "foreign";

type Summary = {
  present: boolean;
  id_type?: IdType | null;
  country?: string | null;
  last4?: string | null;
  mode?: string;
};

/** The calls differ by who is asking (a team member of the business, or one of its clients);
 * the card is the same. */
export type IdentityApi = {
  load: () => Promise<Summary>;
  save: (body: { id_type: IdType; number: string; country: string | null }) => Promise<Summary>;
  remove: () => Promise<void>;
  reveal: () => Promise<string>;
};

/** "My ID number": masked, shown only when asked, saved with the check digit verified. */
export function IdentityCard({ palette, calls, intro }: { palette: Palette; calls: IdentityApi; intro?: string }) {
  const t = useTranslations("identity");
  const load = useCallback(() => calls.load(), [calls]);
  const { data, error: loadError, reload } = useLoad(load);
  const [editing, setEditing] = useState(false);
  const [idType, setIdType] = useState<IdType>("il_id");
  const [number, setNumber] = useState("");
  const [country, setCountry] = useState("");
  const [shown, setShown] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (loadError !== undefined && !data) return <LoadError palette={palette} onRetry={() => void reload()} />;
  // A business that does not ask its clients for an ID shows nothing here.
  if (!data || data.mode === "off") return null;

  const fail = (caught: unknown) => {
    const detail = caught instanceof ApiError ? caught.detail : undefined;
    const known = ["invalid_id_number", "invalid_id_country", "id_number_in_use", "client_id_off"];
    setError(t(`errors.${known.includes(detail ?? "") ? detail : "generic"}` as "errors.generic"));
  };

  const save = async () => {
    if (idType === "il_id" && !israeliIdValid(number)) return setError(t("errors.invalid_id_number"));
    if (idType !== "il_id" && !/^[A-Za-z]{2}$/.test(country.trim())) return setError(t("errors.invalid_id_country"));
    setBusy(true);
    setError(null);
    try {
      await calls.save({ id_type: idType, number, country: idType === "il_id" ? null : country.trim().toUpperCase() });
      setEditing(false);
      setNumber("");
      setShown(null);
      await reload();
    } catch (caught) {
      fail(caught);
    } finally {
      setBusy(false);
    }
  };

  const toggle = async () => {
    if (shown) return setShown(null);
    try {
      setShown(await calls.reveal());
    } catch (caught) {
      fail(caught);
    }
  };

  const remove = async () => {
    try {
      await calls.remove();
      setShown(null);
      await reload();
    } catch (caught) {
      fail(caught);
    }
  };

  return (
    <Card palette={palette}>
      <SectionTitle title={t("mine.title")} palette={palette} />
      <Text style={[styles.muted, { color: palette.muted }]}>{intro ?? t("mine.intro")}</Text>
      {data.present ? (
        <>
          <Text style={{ color: palette.muted }}>{t(`types.${data.id_type ?? "il_id"}`)}</Text>
          <Text accessibilityLiveRegion="polite" style={{ color: palette.foreground, fontSize: 17, writingDirection: "ltr" }}>
            {shown ?? maskedId(data.last4 ?? "")}
          </Text>
          <Button label={shown ? t("hide") : t("show")} variant="secondary" palette={palette} onPress={() => void toggle()} />
        </>
      ) : (
        <Text style={{ color: palette.muted }}>{t("none")}</Text>
      )}
      <ErrorText message={error} palette={palette} />
      {editing ? (
        <>
          <SegmentedControl
            label={t("type")}
            options={(["il_id", "passport", "foreign"] as const).map((value) => ({ value, label: t(`types.${value}`) }))}
            value={idType}
            onChange={(value) => setIdType(value as IdType)}
          />
          <Field
            label={t("number")}
            palette={palette}
            value={number}
            onChangeText={setNumber}
            keyboardType={idType === "il_id" ? "number-pad" : "default"}
            autoCapitalize="characters"
            maxLength={idType === "il_id" ? 11 : 24}
            dir="ltr"
          />
          {idType !== "il_id" && (
            <Field label={t("country")} hint={t("countryHint")} palette={palette} value={country} onChangeText={setCountry} autoCapitalize="characters" maxLength={2} dir="ltr" />
          )}
          <Button label={t("save")} palette={palette} busy={busy} onPress={() => void save()} />
          <Button label={t("cancel")} variant="secondary" palette={palette} onPress={() => setEditing(false)} />
        </>
      ) : (
        <>
          <Button label={data.present ? t("replace") : t("add")} palette={palette} onPress={() => setEditing(true)} />
          {data.present && <Button label={t("remove")} variant="danger" palette={palette} onPress={() => void remove()} />}
        </>
      )}
    </Card>
  );
}

function check(result: { response: Response; error?: unknown }): void {
  if (!result.response.ok) {
    const detail = (result.error as { detail?: unknown } | undefined)?.detail;
    throw new ApiError(result.response.status, typeof detail === "string" ? detail : undefined);
  }
}

/** The signed-in client's own ID number in the current business (hidden when it does not ask). */
export function ClientIdentityCard() {
  const { api, scope, palette } = useBusiness();
  const ctx = useDataContext();
  const t = useTranslations("identity.mine");
  const calls = useMemo<IdentityApi>(
    () => ({
      load: async () => (ctx ? fetchIdentity(ctx) : unwrap(await api.GET("/client/identity", { params: scope }))),
      save: async (body) => {
        const saved = unwrap(await api.PUT("/client/identity", { params: scope, body }));
        if (ctx) await forgetShared(ctx, "identity");
        return saved;
      },
      remove: async () => {
        check(await api.DELETE("/client/identity", { params: scope }));
        if (ctx) await forgetShared(ctx, "identity");
      },
      reveal: async () => unwrap(await api.POST("/client/identity/reveal", { params: scope })).number,
    }),
    [api, scope, ctx],
  );
  return <IdentityCard palette={palette} calls={calls} intro={t("optionalClient")} />;
}

/** The signed-in team member's own ID number (payroll and legal forms). */
export function StaffIdentityCard() {
  const { api, tenant, palette } = useStaff();
  const calls = useMemo<IdentityApi>(() => {
    const params = { header: { "X-Tenant-Id": tenant?.id ?? "" } };
    return {
      load: async () => unwrap(await api.GET("/me/identity", { params })),
      save: async (body) => unwrap(await api.PUT("/me/identity", { params, body })),
      remove: async () => check(await api.DELETE("/me/identity", { params })),
      reveal: async () => unwrap(await api.POST("/me/identity/reveal", { params })).number,
    };
  }, [api, tenant?.id]);
  if (!tenant) return null;
  return <IdentityCard palette={palette} calls={calls} />;
}
