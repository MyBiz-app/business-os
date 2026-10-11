import type { components } from "@business-os/api-client";
import Ionicons from "@expo/vector-icons/Ionicons";
import { addDays, formatDay, formatTime, todayIn } from "@business-os/i18n/dates";
import { router } from "expo-router";
import { useCallback, useState } from "react";
import { Linking, Text, View } from "react-native";
import { useLocale, useTranslations } from "use-intl";

import { BackBar, Badge, PillRow, SectionTitle } from "@business-os/app-kit/components/rows";
import { Button, Card, ErrorText, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { googleMapsLink, wazeLink } from "@business-os/app-kit/lib/maps";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { useBusiness } from "@/providers/business-provider";

type Job = components["schemas"]["Job"];
type JobStatus = Job["job_status"];

const STEPS: JobStatus[] = ["scheduled", "on_the_way", "in_progress", "done"];
const TONE = { scheduled: "muted", on_the_way: "primary", in_progress: "primary", done: "success" } as const;
const DAYS = 7;

/** A technician's day of on-site jobs (#42), in order: where, who, navigate, call, and the job's
 * progress (on my way → start → done). Managers can see the whole team's day. */
export default function Jobs() {
  const t = useTranslations("jobs");
  const tToday = useTranslations("business.today");
  const locale = useLocale();
  const { api, scope, tenant, palette, can } = useBusiness();
  const tenantId = tenant?.id;
  const today = tenant ? todayIn(tenant.time_zone) : "";
  const [day, setDay] = useState(today);
  const [everyone, setEveryone] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!tenantId || !day) return [] as Job[];
    return unwrap(await api.GET("/jobs", { params: { ...scope, query: { date: day, everyone } } }));
  }, [api, scope, tenantId, day, everyone]);
  const { data: jobs, loading, reload } = useLoad(load);
  if (!tenant) return null;
  const time = (iso: string) => formatTime(iso, locale, tenant.time_zone);

  const move = async (job: Job, status: JobStatus) => {
    setBusy(job.session_id);
    setError(null);
    try {
      unwrap(await api.POST("/jobs/{session_id}/status", { params: { ...scope, path: { session_id: job.session_id } }, body: { status } }));
      await reload();
    } catch {
      setError(t("statusFailed"));
    } finally {
      setBusy(null);
    }
  };

  const days = Array.from({ length: DAYS }, (_, i) => addDays(today, i)).map((value) => ({
    value,
    label: formatDay(value, locale, { day: "numeric" }),
    sublabel: value === today ? tToday("title") : formatDay(value, locale, { weekday: "short" }),
    accessibilityLabel: formatDay(value, locale, { weekday: "long", day: "numeric", month: "long" }),
  }));

  return (
    <Screen palette={palette} refreshing={loading} onRefresh={() => void reload()}>
      <BackBar label={tToday("title")} palette={palette} onPress={() => router.back()} />
      <Heading palette={palette}>{everyone ? t("teamDay") : t("myDay")}</Heading>
      <PillRow label={tToday("days")} options={days} value={day} onChange={setDay} palette={palette} />
      {can("bookings.manage") && (
        <PillRow
          label={t("whose")}
          palette={palette}
          value={everyone ? "team" : "mine"}
          onChange={(value) => setEveryone(value === "team")}
          options={[
            { value: "mine", label: t("mine") },
            { value: "team", label: t("team") },
          ]}
        />
      )}
      <ErrorText message={error} palette={palette} />
      {jobs && jobs.length === 0 && (
        <Card palette={palette}>
          <Text style={[styles.muted, { color: palette.muted }]}>{t("none")}</Text>
        </Card>
      )}
      {jobs?.map((job, index) => {
        const step = STEPS.indexOf(job.job_status);
        const next = STEPS[step + 1];
        return (
          <Card key={job.session_id} palette={palette}>
            <SectionTitle title={`${index + 1}. ${time(job.starts_at)} · ${job.service_name}`} palette={palette} />
            <View style={{ flexDirection: "row", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
              <Badge label={t(`statuses.${job.job_status}`)} tone={TONE[job.job_status]} palette={palette} />
              {everyone && job.technician_name ? <Text style={{ color: palette.muted }}>{job.technician_name}</Text> : null}
              {job.travel_minutes > 0 && (
                <Text style={{ color: palette.muted }}>{t("leaveBy", { time: time(new Date(Date.parse(job.starts_at) - job.travel_minutes * 60000).toISOString()) })}</Text>
              )}
            </View>
            {job.client_name ? (
              <Text style={{ color: palette.foreground, fontWeight: "700", textAlign: "left" }}>{job.client_name}</Text>
            ) : null}
            {job.address ? (
              <View style={{ flexDirection: "row", gap: 6, alignItems: "flex-start" }}>
                <Ionicons name="location-outline" size={18} color={palette.primary} />
                <Text style={{ color: palette.foreground, flex: 1, textAlign: "left" }}>{job.address}</Text>
              </View>
            ) : null}
            {job.address_notes ? <Text style={[styles.muted, { color: palette.muted }]}>{job.address_notes}</Text> : null}
            <View style={{ flexDirection: "row", gap: 8, flexWrap: "wrap" }}>
              {job.address && (
                <View style={{ flex: 1, minWidth: 120 }}>
                  <Button label="Waze" variant="secondary" palette={palette} onPress={() => void Linking.openURL(wazeLink(job.address!))} />
                </View>
              )}
              {job.address && (
                <View style={{ flex: 1, minWidth: 120 }}>
                  <Button label="Google Maps" variant="secondary" palette={palette} onPress={() => void Linking.openURL(googleMapsLink(job.address!))} />
                </View>
              )}
              {job.client_phone && (
                <View style={{ flex: 1, minWidth: 120 }}>
                  <Button
                    label={t("call")}
                    accessibilityLabel={`${t("call")} ${job.client_name ?? ""}`}
                    variant="secondary"
                    palette={palette}
                    onPress={() => void Linking.openURL(`tel:${job.client_phone}`)}
                  />
                </View>
              )}
            </View>
            {next && (
              <Button
                label={t(`actions.${next as Exclude<JobStatus, "scheduled">}`)}
                accessibilityLabel={`${t(`actions.${next as Exclude<JobStatus, "scheduled">}`)} – ${job.client_name ?? job.service_name}`}
                palette={palette}
                busy={busy === job.session_id}
                onPress={() => void move(job, next)}
              />
            )}
            <Button label={t("open")} variant="secondary" palette={palette} onPress={() => router.push(`/session/${job.session_id}`)} />
          </Card>
        );
      })}
    </Screen>
  );
}
