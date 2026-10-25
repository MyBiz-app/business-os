import { CameraView, useCameraPermissions } from "expo-camera";
import { useEffect, useRef } from "react";
import { Modal, StyleSheet, View } from "react-native";
import { Text } from "@business-os/app-kit/components/text";
import { useTranslations } from "use-intl";

import { Button } from "@business-os/app-kit/components/ui";
import { joinCodeFromScan } from "@business-os/app-kit/lib/join-code";
import { fixedColors, type Palette } from "@business-os/app-kit/lib/theme";

/** Full-screen camera that reads a business's QR code and hands back its join code. */
export function JoinScanner({ visible, palette, onCode, onClose }: { visible: boolean; palette: Palette; onCode: (code: string) => void; onClose: () => void }) {
  const t = useTranslations("client.join");
  const [permission, requestPermission] = useCameraPermissions();
  const done = useRef(false);

  useEffect(() => {
    if (visible) {
      done.current = false;
      if (permission && !permission.granted && permission.canAskAgain) void requestPermission();
    }
  }, [visible, permission, requestPermission]);

  return (
    <Modal visible={visible} animationType="slide" presentationStyle="fullScreen" onRequestClose={onClose}>
      <View style={[local.fill, { backgroundColor: palette.background }]}>
        {permission?.granted ? (
          <CameraView
            style={local.fill}
            facing="back"
            barcodeScannerSettings={{ barcodeTypes: ["qr"] }}
            onBarcodeScanned={({ data }) => {
              // The camera fires many times a second; take the first readable code only.
              const code = joinCodeFromScan(data);
              if (!code || done.current) return;
              done.current = true;
              onCode(code);
            }}
          />
        ) : (
          <View style={local.denied}>
            <Text style={[local.hint, { color: palette.foreground }]}>{t("scanDenied")}</Text>
          </View>
        )}
        <View style={local.bar}>
          {permission?.granted ? <Text style={local.overlayHint}>{t("scanHint")}</Text> : null}
          <Button label={t("scanClose")} variant="secondary" palette={palette} onPress={onClose} />
        </View>
      </View>
    </Modal>
  );
}

const local = StyleSheet.create({
  fill: { flex: 1 },
  denied: { flex: 1, alignItems: "center", justifyContent: "center", padding: 24 },
  hint: { fontSize: 15, textAlign: "center" },
  bar: { position: "absolute", start: 16, end: 16, bottom: 32, gap: 12 },
  overlayHint: { color: fixedColors.white, textAlign: "center", fontSize: 15, textShadowColor: fixedColors.black, textShadowRadius: 6 },
});
