import Ionicons from "@expo/vector-icons/Ionicons";
import { Modal, Pressable, ScrollView, StyleSheet, View } from "react-native";
import { useTranslations } from "use-intl";

import { Text } from "@business-os/app-kit/components/text";
import { Button, Heading, styles as ui } from "@business-os/app-kit/components/ui";
import type { Palette } from "@business-os/app-kit/lib/theme";
import { SessionFriends } from "@/components/session-friends";

type Props = {
  visible: boolean;
  onClose: () => void;
  sessionId: string;
  title: string;
  when: string;
  description: string | null;
  coach: string | null;
  place: string;
  booked: boolean;
  /** Whether the category keeps participant lists (and so friends). */
  social: boolean;
  /** The card's own book / waitlist / cancel button, so it works from here too. */
  action: React.ReactNode;
  palette: Palette;
};

/** A class opened: what it is, who teaches, who is coming (tap a person for their profile), register or invite. */
export function SessionSheet({ visible, onClose, sessionId, title, when, description, coach, place, booked, social, action, palette }: Props) {
  const t = useTranslations("friends");
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={s.scrim} onPress={onClose} accessibilityLabel={t("close")} />
      <View style={[s.sheet, { backgroundColor: palette.surface, borderColor: palette.border }]}>
        <View style={s.head}>
          <View style={{ flex: 1 }}>
            <Heading palette={palette} level={2}>
              {title}
            </Heading>
            <Text style={[ui.muted, { color: palette.muted }]}>{when}</Text>
          </View>
          <Pressable accessibilityRole="button" accessibilityLabel={t("close")} onPress={onClose} hitSlop={12}>
            <Ionicons name="close" size={24} color={palette.foreground} />
          </Pressable>
        </View>
        <ScrollView contentContainerStyle={s.body}>
          {coach ? <Text style={[ui.muted, { color: palette.foreground }]}>{coach}</Text> : null}
          {place ? <Text style={[ui.muted, { color: palette.muted }]}>{place}</Text> : null}
          {description ? (
            <>
              <Text style={[ui.h2, { color: palette.foreground }]}>{t("aboutClass")}</Text>
              <Text style={[ui.muted, { color: palette.foreground }]}>{description}</Text>
            </>
          ) : null}
          {social && <SessionFriends sessionId={sessionId} alwaysOpen canInviteFriends={booked} onLeave={onClose} />}
        </ScrollView>
        <View style={s.footer}>{action}</View>
      </View>
    </Modal>
  );
}

const s = StyleSheet.create({
  scrim: { flex: 1, backgroundColor: "rgba(0,0,0,0.45)" },
  sheet: { maxHeight: "85%", borderTopLeftRadius: 28, borderTopRightRadius: 28, borderWidth: 1, padding: 20, gap: 12 },
  head: { flexDirection: "row", alignItems: "flex-start", gap: 12 },
  body: { gap: 10, paddingBottom: 8 },
  footer: { gap: 8 },
});
