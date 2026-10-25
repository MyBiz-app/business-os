import { useEffect, useState } from "react";
import { Text } from "@business-os/app-kit/components/text";
import { Card, Heading, styles } from "@business-os/app-kit/components/ui";
import { apiClient, unwrap } from "@business-os/app-kit/lib/api";
import { FRESH_MS, queryClient } from "@business-os/app-kit/lib/query-client";
import type { Palette } from "@business-os/app-kit/lib/theme";
import { useLocale, useTranslations } from "use-intl";

/** The business's cancellation rules in words (R32): what is free, what a late cancellation or a
 * no-show costs. Shown at the first sign-up and on the profile, so nobody learns them from a
 * penalty. Renders nothing while loading or when the rules cannot be read. */
export function CancellationPolicyCard({ palette, tenantId }: { palette: Palette; tenantId: string }) {
  const t = useTranslations("client.cancellationPolicy");
  const locale = useLocale();
  const [policy, setPolicy] = useState<{ he: string; en: string } | null>(null);

  useEffect(() => {
    let live = true;
    queryClient
      .fetchQuery({
        queryKey: ["cancellation-policy", tenantId],
        queryFn: async () => unwrap(await apiClient().GET("/client/cancellation-policy", { params: { header: { "X-Tenant-Id": tenantId } } })),
        staleTime: FRESH_MS,
      })
      .then((result) => live && setPolicy(result.text))
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [tenantId]);

  if (!policy) return null;
  return (
    <Card palette={palette}>
      <Heading palette={palette} level={2}>{t("title")}</Heading>
      <Text style={[styles.muted, { color: palette.muted }]}>{locale === "he" ? policy.he : policy.en}</Text>
    </Card>
  );
}
