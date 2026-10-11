import type { components } from "@business-os/api-client";
import { useState } from "react";
import { Text, View } from "react-native";
import { useTranslations } from "use-intl";

import { PillRow } from "./rows";
import { Button, ErrorText, Field, styles } from "./ui";
import type { Palette } from "../lib/theme";

type Definition = components["schemas"]["ClientFieldDefinition"];
type Dependent = components["schemas"]["Dependent"];
export type DependentBody = components["schemas"]["DependentCreate"];

type Props = {
  kind: "pet" | "child";
  fields: Definition[];
  /** Editing this one; adding a new one when absent. */
  dependent?: Dependent;
  palette: Palette;
  /** Saves the values; throws to show a failure. */
  onSave: (body: DependentBody) => Promise<void>;
};

const NOT_SET = "";

/** A pet or child: name, date of birth, the industry's details about them and notes. Used by the
 * client app (my pets / children) and the business app (a client's card). */
export function DependentForm({ kind, fields, dependent, palette, onSave }: Props) {
  const t = useTranslations("dependents");
  const tFields = useTranslations("clientFields");
  const [name, setName] = useState(dependent?.name ?? "");
  const [birthDate, setBirthDate] = useState(dependent?.birth_date ?? "");
  const [notes, setNotes] = useState(dependent?.notes ?? "");
  const [details, setDetails] = useState<Record<string, string>>(() =>
    Object.fromEntries(Object.entries(dependent?.details ?? {}).map(([k, v]) => [k, String(v)])),
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Labels are shared with the client fields (clientFields.<key>).
  const label = (key: string) => tFields(key as "goal");

  const save = async () => {
    if (!name.trim()) return setError(t("nameRequired"));
    if (birthDate && !/^\d{4}-\d{2}-\d{2}$/.test(birthDate)) return setError(t("dateFormat"));
    setBusy(true);
    setError(null);
    try {
      await onSave({
        name,
        birth_date: birthDate || null,
        notes: notes || null,
        details: Object.fromEntries(fields.map((f) => [f.key, details[f.key] || null])),
      });
      if (!dependent) {
        setName("");
        setBirthDate("");
        setNotes("");
        setDetails({});
      }
    } catch {
      setError(t("saveFailed"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <View style={{ gap: 12 }}>
      <Field label={t("name")} palette={palette} value={name} onChangeText={setName} maxLength={80} />
      <Field
        label={t("birthDate")}
        hint={t("dateHint")}
        palette={palette}
        value={birthDate}
        onChangeText={setBirthDate}
        placeholder="2020-05-31"
        inputMode="numeric"
        maxLength={10}
      />
      {fields.map((field) =>
        field.kind === "select" ? (
          <View key={field.key} style={{ gap: 6 }}>
            <Text style={[styles.label, { color: palette.foreground }]}>{label(field.key)}</Text>
            <PillRow
              label={label(field.key)}
              palette={palette}
              value={details[field.key] ?? NOT_SET}
              onChange={(value) => setDetails((current) => ({ ...current, [field.key]: value }))}
              options={[
                { value: NOT_SET, label: tFields("notSet") },
                ...field.options.map((option) => ({
                  value: option,
                  label: tFields(`${field.key}_options.${option}` as "goal_options.strength"),
                })),
              ]}
            />
          </View>
        ) : (
          <Field
            key={field.key}
            label={label(field.key)}
            palette={palette}
            value={details[field.key] ?? ""}
            onChangeText={(value) => setDetails((current) => ({ ...current, [field.key]: value }))}
            inputMode={field.kind === "number" ? "numeric" : undefined}
            multiline={field.kind === "long_text"}
            maxLength={field.max_length}
          />
        ),
      )}
      <Field label={t("notes")} palette={palette} value={notes} onChangeText={setNotes} multiline maxLength={2000} />
      <ErrorText message={error} palette={palette} />
      <Button
        label={dependent ? t("save") : t(`add.${kind}`)}
        palette={palette}
        busy={busy}
        onPress={() => void save()}
      />
    </View>
  );
}
