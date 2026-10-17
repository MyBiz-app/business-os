import { router } from "expo-router";
import { useCallback, useState } from "react";
import { View } from "react-native";
import { Text } from "@business-os/app-kit/components/text";
import { useTranslations } from "use-intl";

import { BackBar, SectionTitle } from "@business-os/app-kit/components/rows";
import { SegmentedControl } from "@business-os/app-kit/components/segmented-control";
import { Button, Card, ErrorText, Field, Heading, Screen } from "@business-os/app-kit/components/ui";
import { ApiError, unwrap } from "@business-os/app-kit/lib/api";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { useStaff } from "@/providers/staff-provider";

type Gender = "female" | "male" | "other";
type Marital = "single" | "married" | "divorced" | "widowed" | "separated";

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

/** The yearly tax-credit declaration (Form 101): the employee answers, signs with their name, and
 * the server computes the credit points. A payroll manager requests it from the team page. */
export default function Form101() {
  const t = useTranslations("business.form101");
  const { api, scope, tenant, palette } = useStaff();
  const year = new Date().getFullYear();
  const load = useCallback(() => api.GET("/me/form101", { params: scope }).then(unwrap), [api, scope]);
  const { data: forms, reload } = useLoad(load);
  const [fullName, setFullName] = useState("");
  const [birthDate, setBirthDate] = useState("");
  const [gender, setGender] = useState<Gender>("female");
  const [address, setAddress] = useState("");
  const [phone, setPhone] = useState("");
  const [marital, setMarital] = useState<Marital>("single");
  const [childYears, setChildYears] = useState("");
  const [singleParent, setSingleParent] = useState(false);
  const [resident, setResident] = useState(true);
  const [immigrant, setImmigrant] = useState("");
  const [soldier, setSoldier] = useState("");
  const [degree, setDegree] = useState("");
  const [disability, setDisability] = useState("");
  const [signedName, setSignedName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  if (!tenant) return null;

  const current = forms?.find((form) => form.tax_year === year);

  const submit = async () => {
    const years = childYears
      .split(/[,\s]+/)
      .filter(Boolean)
      .map(Number);
    const dates = [birthDate, immigrant, soldier];
    if (
      !fullName.trim() ||
      !address.trim() ||
      signedName.trim().length < 2 ||
      !ISO_DATE.test(birthDate) ||
      dates.some((value) => value && !ISO_DATE.test(value)) ||
      years.some((value) => !Number.isInteger(value) || value < 1990 || value > year)
    ) {
      return setError(t("errors.invalid"));
    }
    setBusy(true);
    setError(null);
    try {
      unwrap(
        await api.PUT("/me/form101/{tax_year}", {
          params: { ...scope, path: { tax_year: year } },
          body: {
            signed_name: signedName.trim(),
            answers: {
              full_name: fullName.trim(),
              birth_date: birthDate,
              gender,
              address: address.trim(),
              phone: phone.trim() || null,
              marital_status: marital,
              children: years.map((birth_year) => ({ birth_year, lives_with_me: true, receives_allowance: false })),
              single_parent: singleParent,
              resident,
              new_immigrant_date: immigrant || null,
              discharged_soldier_date: soldier || null,
              academic_degree_year: degree ? Number(degree) : null,
              disability_percent: disability ? Number(disability) : 0,
              eligible_locality: false,
              other_income: { kind: "none", tax_coordination: false },
            },
          },
        }),
      );
      setDone(true);
      await reload();
    } catch (caught) {
      setError(t(caught instanceof ApiError && caught.status === 422 ? "errors.invalid" : "errors.generic"));
    } finally {
      setBusy(false);
    }
  };

  const yesNo = (value: boolean, change: (next: boolean) => void, label: string) => (
    <SegmentedControl
      label={label}
      options={[
        { value: "yes", label: t("yes") },
        { value: "no", label: t("no") },
      ]}
      value={value ? "yes" : "no"}
      onChange={(next) => change(next === "yes")}
    />
  );

  return (
    <Screen palette={palette}>
      <BackBar label={t("back")} palette={palette} onPress={() => router.back()} />
      <Heading palette={palette}>{t("title", { year })}</Heading>
      <Text style={{ color: palette.muted }}>{t("intro")}</Text>
      {current?.status === "submitted" && (
        <Text accessibilityLiveRegion="polite" style={{ color: palette.primary }}>
          {done ? t("signedNow") : t("signedBefore", { name: current.signed_name ?? "" })}
        </Text>
      )}

      <SectionTitle title={t("personal")} palette={palette} />
      <Card palette={palette}>
        <Field label={t("fullName")} palette={palette} value={fullName} onChangeText={setFullName} autoComplete="name" />
        <Field label={t("birthDate")} hint={t("dateHint")} palette={palette} value={birthDate} onChangeText={setBirthDate} placeholder="1990-03-12" keyboardType="numbers-and-punctuation" maxLength={10} style={{ writingDirection: "ltr" }} />
        <SegmentedControl
          label={t("gender")}
          options={(["female", "male", "other"] as const).map((value) => ({ value, label: t(`genders.${value}`) }))}
          value={gender}
          onChange={(value) => setGender(value as Gender)}
        />
        <Field label={t("address")} palette={palette} value={address} onChangeText={setAddress} autoComplete="street-address" />
        <Field label={t("phone")} palette={palette} value={phone} onChangeText={setPhone} keyboardType="phone-pad" style={{ writingDirection: "ltr" }} />
        <SegmentedControl
          label={t("marital")}
          options={(["single", "married", "divorced", "widowed", "separated"] as const).map((value) => ({ value, label: t(`maritals.${value}`) }))}
          value={marital}
          onChange={(value) => setMarital(value as Marital)}
        />
      </Card>

      <SectionTitle title={t("credits")} palette={palette} />
      <Card palette={palette}>
        {yesNo(resident, setResident, t("resident"))}
        <Field label={t("children")} hint={t("childrenHint")} palette={palette} value={childYears} onChangeText={setChildYears} keyboardType="numbers-and-punctuation" style={{ writingDirection: "ltr" }} />
        {yesNo(singleParent, setSingleParent, t("singleParent"))}
        <Field label={t("immigrant")} hint={t("dateHint")} palette={palette} value={immigrant} onChangeText={setImmigrant} keyboardType="numbers-and-punctuation" maxLength={10} style={{ writingDirection: "ltr" }} />
        <Field label={t("soldier")} hint={t("dateHint")} palette={palette} value={soldier} onChangeText={setSoldier} keyboardType="numbers-and-punctuation" maxLength={10} style={{ writingDirection: "ltr" }} />
        <Field label={t("degree")} palette={palette} value={degree} onChangeText={setDegree} keyboardType="number-pad" maxLength={4} style={{ writingDirection: "ltr" }} />
        <Field label={t("disability")} palette={palette} value={disability} onChangeText={setDisability} keyboardType="number-pad" maxLength={3} style={{ writingDirection: "ltr" }} />
      </Card>

      <SectionTitle title={t("sign")} palette={palette} />
      <Card palette={palette}>
        <Text style={{ color: palette.muted }}>{t("declaration")}</Text>
        <Field label={t("signedName")} palette={palette} value={signedName} onChangeText={setSignedName} autoComplete="name" />
        <ErrorText message={error} palette={palette} />
        <Button label={current?.status === "submitted" ? t("signAgain") : t("signSubmit")} palette={palette} busy={busy} onPress={() => void submit()} />
      </Card>
      <View />
    </Screen>
  );
}
