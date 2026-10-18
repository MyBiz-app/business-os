import { useEffect, useMemo, useState } from "react";
import { View } from "react-native";
import { useTranslations } from "use-intl";

import { apiClient } from "../lib/api";
import { type AddressValue } from "../lib/address";
import type { Palette } from "../lib/theme";
import { ListRow } from "./rows";
import { Button, Field } from "./ui";

type Suggestion = { code: number; label: string };

/** Official names that contain what was typed (the API's /geo lists), after a short pause. */
function useSuggestions(load: ((query: string) => Promise<Suggestion[]>) | null, query: string, active: boolean): Suggestion[] {
  const [found, setFound] = useState<Suggestion[]>([]);
  useEffect(() => {
    if (!load || !active || query.trim() === "") {
      setFound([]);
      return;
    }
    let current = true;
    const timer = setTimeout(() => {
      void load(query)
        .then((rows) => current && setFound(rows))
        .catch(() => current && setFound([]));
    }, 200);
    return () => {
      current = false;
      clearTimeout(timer);
    };
  }, [load, query, active]);
  return found;
}

/**
 * One address with the official lists: type a city and pick it, then a street of that city, then
 * a house number and details. "My street is not listed" lets the person type it (flagged for
 * review). The screen keeps the value and sends it with `addressBody` (lib/address.ts).
 */
export function AddressPicker({ palette, value, onChange }: { palette: Palette; value: AddressValue; onChange: (value: AddressValue) => void }) {
  const t = useTranslations("address");
  const api = useMemo(() => apiClient(), []);
  const [unlisted, setUnlisted] = useState(value.streetUnlisted !== "");

  const loadCities = useMemo(
    () => async (q: string) => {
      const { data } = await api.GET("/geo/cities", { params: { query: { q, limit: 6 } } });
      return (data ?? []).map((city) => ({ code: city.code, label: city.name_he }));
    },
    [api],
  );
  const cityCode = value.cityCode;
  const loadStreets = useMemo(
    () =>
      cityCode === null
        ? null
        : async (q: string) => {
            const { data } = await api.GET("/geo/cities/{city_code}/streets", { params: { path: { city_code: cityCode }, query: { q, limit: 6 } } });
            return (data ?? []).map((street) => ({ code: street.code, label: street.name_he }));
          },
    [api, cityCode],
  );

  const cities = useSuggestions(loadCities, value.cityText, value.cityCode === null);
  const streets = useSuggestions(loadStreets, value.streetText, value.streetCode === null && !unlisted);

  return (
    <View style={{ gap: 12 }}>
      <Field label={t("city")} palette={palette} value={value.cityText} placeholder={t("cityPlaceholder")} maxLength={80} onChangeText={(cityText) => onChange({ ...value, cityText, cityCode: null, streetCode: null, streetText: "" })} />
      {value.cityCode === null && cities.map((city) => <ListRow key={city.code} palette={palette} title={city.label} onPress={() => onChange({ ...value, cityCode: city.code, cityText: city.label })} />)}
      {unlisted ? (
        <>
          <Field label={t("unlistedStreet")} hint={t("unlistedNote")} palette={palette} value={value.streetUnlisted} maxLength={120} onChangeText={(streetUnlisted) => onChange({ ...value, streetUnlisted, streetCode: null, streetText: "" })} />
          <Button label={t("backToList")} variant="secondary" palette={palette} onPress={() => { setUnlisted(false); onChange({ ...value, streetUnlisted: "" }); }} />
        </>
      ) : (
        <>
          <Field label={t("street")} palette={palette} value={value.streetText} editable={value.cityCode !== null} placeholder={value.cityCode === null ? t("streetNeedsCity") : t("streetPlaceholder")} maxLength={120} onChangeText={(streetText) => onChange({ ...value, streetText, streetCode: null })} />
          {value.streetCode === null && streets.map((street) => <ListRow key={street.code} palette={palette} title={street.label} onPress={() => onChange({ ...value, streetCode: street.code, streetText: street.label })} />)}
          {value.cityCode !== null && <Button label={t("unlisted")} variant="secondary" palette={palette} onPress={() => { setUnlisted(true); onChange({ ...value, streetCode: null, streetText: "" }); }} />}
        </>
      )}
      <Field label={t("houseNumber")} palette={palette} value={value.houseNumber} maxLength={20} onChangeText={(houseNumber) => onChange({ ...value, houseNumber })} />
      <Field label={`${t("details")} (${t("optional")})`} palette={palette} value={value.details} maxLength={100} onChangeText={(details) => onChange({ ...value, details })} />
    </View>
  );
}
