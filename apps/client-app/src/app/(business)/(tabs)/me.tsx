import { useEffect, useState } from "react";
import { router } from "expo-router";
import { View } from "react-native";
import { Text } from "@business-os/app-kit/components/text";
import { useTranslations } from "use-intl";

import { Button, Card, ErrorText, Field, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { ListRow, RowGroup } from "@business-os/app-kit/components/rows";
import { SegmentedControl } from "@business-os/app-kit/components/segmented-control";
import { PreferencesCard } from "@business-os/app-kit/components/preferences-card";
import { ApiError, unwrap } from "@business-os/app-kit/lib/api";
import { AreaSwitcher } from "@/components/area-switcher";
import { BrandColorCard } from "@/components/brand-color-card";
import { StaffIdentityCard } from "@/components/identity-card";
import { useStaff } from "@/providers/staff-provider";
import { useSession } from "@business-os/app-kit/providers/session-provider";


/** The staff member's own settings: name, shift emails, business, language, appearance, sign out. */
export default function Me() {
  const t = useTranslations("business.me");
  const tRoles = useTranslations("roles");
  const tSchedule = useTranslations("business.schedule");
  const tAvailability = useTranslations("business.availability");
  const tClock = useTranslations("business.timeClock");
  const tForm = useTranslations("business.form101");
  const tDocuments = useTranslations("business.myDocuments");
  const { palette, tenant, api, refresh, branches, branch, selectBranch, can } = useStaff();
  // Solo mode: a one-person business doesn't see shifts, the time clock or employee paperwork.
  const solo = tenant?.business_size === "solo";
  const { session } = useSession();
  const [name, setName] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [emailRoster, setEmailRoster] = useState<boolean | null>(null);
  const tClosure = useTranslations("closure");
  const [confirmName, setConfirmName] = useState("");
  const [closing, setClosing] = useState(false);
  const [closeError, setCloseError] = useState<string | null>(null);

  useEffect(() => {
    api
      .GET("/me")
      .then(unwrap)
      .then((me) => {
        setEmailRoster(me.email_roster ?? true);
        // Start from the saved name; what they already typed is kept.
        setName((typed) => typed ?? me.full_name ?? "");
      })
      .catch(() => undefined);
  }, [api]);

  const chooseRosterEmails = async (on: boolean) => {
    const previous = emailRoster;
    setEmailRoster(on);
    try {
      unwrap(await api.PATCH("/me", { body: { email_roster: on } }));
    } catch {
      setEmailRoster(previous);
    }
  };

  const closeBusiness = async () => {
    if (!tenant) return;
    setClosing(true);
    setCloseError(null);
    try {
      unwrap(await api.POST("/tenants/current/closure", { params: { header: { "X-Tenant-Id": tenant.id } }, body: { confirm_name: confirmName } }));
      await refresh();
      router.replace("/business");
    } catch (error) {
      const detail = error instanceof ApiError ? error.detail : undefined;
      setCloseError(tClosure(detail === "name_mismatch" || detail === "already_closed" || detail === "owner_only" ? `errors.${detail}` : "errors.generic"));
    } finally {
      setClosing(false);
    }
  };

  const save = async () => {
    setSaving(true);
    try {
      unwrap(await api.PATCH("/me", { body: { full_name: name ?? "" } }));
      await refresh();
    } finally {
      setSaving(false);
    }
  };

  return (
    <Screen palette={palette}>
      <Heading palette={palette}>{t("title")}</Heading>

      <Card palette={palette}>
        <Text style={[styles.muted, { color: palette.muted, writingDirection: "ltr" }]}>
          {session?.user.email}
        </Text>
        {tenant && <Text style={{ color: palette.foreground, fontWeight: "500" }}>{tenant.name}</Text>}
        {tenant && (
          <Text style={[styles.muted, { color: palette.muted }]}>
            {t("role", { role: tenant.custom_role_name ?? tRoles(tenant.role as "owner") })}
          </Text>
        )}
      </Card>

      <RowGroup palette={palette}>
        {can("schedule.read") && !solo ? <ListRow palette={palette} title={tSchedule("open")} onPress={() => router.push("/staff-schedule")} /> : null}
        {can("schedule.read") && !solo ? <ListRow palette={palette} title={tClock("open")} onPress={() => router.push("/time-clock")} /> : null}
        {can("schedule.read") ? <ListRow palette={palette} title={tAvailability("open")} onPress={() => router.push("/availability")} /> : null}
        {!solo ? <ListRow palette={palette} title={tDocuments("open")} onPress={() => router.push("/my-documents")} /> : null}
        {!solo ? <ListRow palette={palette} title={tForm("open")} onPress={() => router.push("/form101")} /> : null}
      </RowGroup>

      <Card palette={palette}>
        <Field
          label={t("name")}
          palette={palette}
          value={name ?? ""}
          onChangeText={setName}
          autoComplete="name"
          onSubmitEditing={() => void save()}
        />
        <Button label={t("save")} palette={palette} busy={saving} onPress={() => void save()} />
      </Card>

      <StaffIdentityCard />

      {can("business.settings") && <BrandColorCard />}

      {emailRoster !== null && (
        <Card palette={palette}>
          <SegmentedControl
            label={t("rosterEmails")}
            value={emailRoster ? "on" : "off"}
            options={[
              { value: "on", label: t("on") },
              { value: "off", label: t("off") },
            ]}
            onChange={(value) => void chooseRosterEmails(value === "on")}
          />
          <Text style={[styles.muted, { color: palette.muted }]}>{t("rosterEmailsHint")}</Text>
        </Card>
      )}

      <AreaSwitcher palette={palette} />

      {branches.length > 1 && (
        <Card palette={palette}>
          <Text style={{ color: palette.foreground, fontWeight: "500" }}>{t("branch")}</Text>
          {[{ id: null, name: t("allBranches") }, ...branches].map((option) => (
            <View key={option.id ?? "all"}>
              <Button
                label={option.name}
                variant={(branch?.id ?? null) === option.id ? "primary" : "secondary"}
                palette={palette}
                onPress={() => void selectBranch(option.id)}
              />
            </View>
          ))}
        </Card>
      )}

      <PreferencesCard palette={palette} />

      {tenant?.role === "owner" && (
        <Card palette={palette}>
          <Text style={{ color: palette.danger, fontWeight: "500" }}>{tClosure("title")}</Text>
          <Text style={[styles.muted, { color: palette.muted }]}>{tClosure("intro", { days: 90 })}</Text>
          <Field
            label={tClosure("confirmLabel", { name: tenant.name })}
            palette={palette}
            value={confirmName}
            onChangeText={setConfirmName}
            autoCapitalize="none"
            autoCorrect={false}
          />
          <ErrorText message={closeError} palette={palette} />
          <Button
            label={tClosure("confirmButton")}
            variant="danger"
            palette={palette}
            busy={closing}
            disabled={confirmName.trim() !== tenant.name}
            onPress={() => void closeBusiness()}
          />
        </Card>
      )}
    </Screen>
  );
}
