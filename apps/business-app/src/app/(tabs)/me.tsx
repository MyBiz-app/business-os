import { useState } from "react";
import { Text, View } from "react-native";
import { useTranslations } from "use-intl";

import { Button, Card, Field, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { PreferencesCard } from "@business-os/app-kit/components/preferences-card";
import { unwrap } from "@business-os/app-kit/lib/api";
import { useBusiness } from "@/providers/business-provider";
import { useSession } from "@business-os/app-kit/providers/session-provider";


/** The staff member's own settings: name, business, language, appearance, sign out. */
export default function Me() {
  const t = useTranslations("business.me");
  const tRoles = useTranslations("roles");
  const { palette, memberships, tenant, select, api, refresh, branches, branch, selectBranch } = useBusiness();
  const { session } = useSession();
  const [name, setName] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

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
        {tenant && <Text style={{ color: palette.foreground, fontWeight: "600" }}>{tenant.name}</Text>}
        {tenant && (
          <Text style={[styles.muted, { color: palette.muted }]}>
            {t("role", { role: tenant.custom_role_name ?? tRoles(tenant.role as "owner") })}
          </Text>
        )}
      </Card>

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

      {(memberships?.length ?? 0) > 1 && (
        <Card palette={palette}>
          <Text style={{ color: palette.foreground, fontWeight: "600" }}>{t("switch")}</Text>
          {(memberships ?? []).map((membership) => (
            <View key={membership.tenant_id}>
              <Button
                label={membership.tenant_name}
                variant={membership.tenant_id === tenant?.id ? "primary" : "secondary"}
                palette={palette}
                onPress={() => void select(membership.tenant_id)}
              />
            </View>
          ))}
        </Card>
      )}

      {branches.length > 1 && (
        <Card palette={palette}>
          <Text style={{ color: palette.foreground, fontWeight: "600" }}>{t("branch")}</Text>
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
    </Screen>
  );
}
