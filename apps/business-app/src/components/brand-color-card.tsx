import { useState } from "react";
import { Pressable, View } from "react-native";
import { Text } from "@business-os/app-kit/components/text";
import { useTranslations } from "use-intl";

import { Button, Card, ErrorText, Field, styles } from "@business-os/app-kit/components/ui";
import { tint } from "@business-os/app-kit/lib/brand";
import { unwrap } from "@business-os/app-kit/lib/api";
import { useBusiness } from "@/providers/business-provider";

const SWATCHES = ["#7c3aed", "#2563eb", "#0891b2", "#16a34a", "#d97706", "#dc2626", "#db2777", "#4f46e5", "#0d9488"];
const HEX = /^#[0-9a-fA-F]{6}$/;

/** "My colors": the business picks its brand color, which themes the client app, the web app and this app. */
export function BrandColorCard() {
  const t = useTranslations("business.me");
  const { palette, tenant, api, refresh } = useBusiness();
  const [draft, setDraft] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [failed, setFailed] = useState(false);
  if (!tenant) return null;

  const current = tenant.primary_color ?? null;
  const value = draft ?? current ?? "";
  const valid = HEX.test(value);

  const save = async (color: string | null) => {
    setSaving(true);
    setFailed(false);
    try {
      unwrap(await api.PATCH("/tenants/current", { params: { header: { "X-Tenant-Id": tenant.id } }, body: { primary_color: color } }));
      setDraft(null);
      await refresh();
    } catch {
      setFailed(true);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card palette={palette}>
      <Text style={{ color: palette.foreground, fontWeight: "600" }}>{t("colors")}</Text>
      <Text style={[styles.muted, { color: palette.muted }]}>{t("colorsHint")}</Text>
      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 10 }}>
        {SWATCHES.map((swatch) => {
          const selected = value.toLowerCase() === swatch;
          return (
            <Pressable
              key={swatch}
              accessibilityRole="radio"
              accessibilityState={{ selected }}
              accessibilityLabel={swatch}
              onPress={() => setDraft(swatch)}
              style={{
                width: 44,
                height: 44,
                borderRadius: 22,
                backgroundColor: swatch,
                borderWidth: 3,
                borderColor: selected ? palette.foreground : tint(swatch, 0.4),
              }}
            />
          );
        })}
      </View>
      <Field
        label={t("colorHex")}
        palette={palette}
        value={value}
        onChangeText={(text) => setDraft(text.startsWith("#") || !text ? text : `#${text}`)}
        autoCapitalize="none"
        autoCorrect={false}
        maxLength={7}
        style={{ writingDirection: "ltr", textAlign: "left" }}
      />
      <ErrorText palette={palette} message={failed ? t("colorsFailed") : null} />
      <Button label={t("save")} palette={palette} busy={saving} disabled={!valid || value.toLowerCase() === current?.toLowerCase()} onPress={() => void save(value.toLowerCase())} />
      {current && <Button label={t("useDefaultColor")} variant="secondary" palette={palette} busy={saving} onPress={() => void save(null)} />}
    </Card>
  );
}
