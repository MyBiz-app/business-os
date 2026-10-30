import { useEffect, useState } from "react";
import { View } from "react-native";
import { useTranslations } from "use-intl";

import { onPushOffer, pushOfferDue, snoozePushOffer } from "../lib/push-offer";
import { registerPushToken } from "../lib/push";
import { useTheme } from "../providers/theme-provider";
import { Sheet } from "./sheet";
import { Text } from "./text";
import { Button } from "./ui";

/**
 * Explains why reminders help, right after the person's booking went through, and only then lets
 * the phone show its own permission prompt. "Not now" is respected for two weeks. Mounted once at the
 * root; screens only call `offerPushAfterBooking()`.
 */
export function PushOfferSheet() {
  const t = useTranslations("pushOffer");
  const { palette } = useTheme();
  const [visible, setVisible] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(
    () =>
      onPushOffer(() => {
        void pushOfferDue().then((due) => due && setVisible(true));
      }),
    [],
  );

  const later = () => {
    setVisible(false);
    void snoozePushOffer();
  };
  const turnOn = async () => {
    setBusy(true);
    await registerPushToken({ ask: true });
    setBusy(false);
    setVisible(false);
    // Whatever the phone answered, the question is settled: do not ask again right away.
    void snoozePushOffer();
  };

  return (
    <Sheet
      visible={visible}
      onClose={later}
      palette={palette}
      title={t("title")}
      footer={
        <View style={{ gap: 8 }}>
          <Button label={t("turnOn")} palette={palette} busy={busy} onPress={() => void turnOn()} />
          <Button label={t("notNow")} variant="quiet" palette={palette} disabled={busy} onPress={later} />
        </View>
      }
    >
      <Text style={{ color: palette.foreground, fontSize: 15, textAlign: "left" }}>{t("body")}</Text>
    </Sheet>
  );
}
