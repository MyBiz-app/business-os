import { locales } from "@business-os/i18n";
import { router } from "expo-router";
import { useState } from "react";
import { Text, View } from "react-native";
import { useTranslations } from "use-intl";

import { SegmentedControl } from "@/components/segmented-control";
import { Button, Card, Field, Heading, Screen, styles } from "@/components/ui";
import { unwrap } from "@/lib/api";
import { supabase } from "@/lib/supabase";
import { useBusiness } from "@/providers/business-provider";
import { useLocaleSetting } from "@/providers/i18n-provider";
import { useSession } from "@/providers/session-provider";
import { useTheme } from "@/providers/theme-provider";

const THEMES = ["system", "light", "dark"] as const;

/** The staff member's own settings: name, business, language, appearance, sign out. */
export default function Me() {
  const t = useTranslations("business.me");
  const tRoles = useTranslations("roles");
  const { palette, memberships, tenant, select, api, refresh } = useBusiness();
  const { session } = useSession();
  const { locale, setLocale } = useLocaleSetting();
  const { preference, setPreference } = useTheme();
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

      <Card palette={palette}>
        <Text style={{ color: palette.foreground, fontWeight: "600" }}>{t("language")}</Text>
        <SegmentedControl
          label={t("language")}
          value={locale}
          options={locales.map((value) => ({ value, label: value === "he" ? "עברית" : "English" }))}
          onChange={(value) => void setLocale(value as "he")}
        />
        <Text style={{ color: palette.foreground, fontWeight: "600" }}>{t("theme")}</Text>
        <SegmentedControl
          label={t("theme")}
          value={preference}
          options={THEMES.map((value) => ({ value, label: t(`themes.${value}`) }))}
          onChange={(value) => setPreference(value as "system")}
        />
      </Card>

      <Button
        label={t("signOut")}
        variant="secondary"
        palette={palette}
        onPress={() => {
          void supabase.auth.signOut().then(() => router.replace("/sign-in"));
        }}
      />
    </Screen>
  );
}
