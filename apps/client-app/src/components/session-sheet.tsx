import { useTranslations } from "use-intl";

import { Sheet } from "@business-os/app-kit/components/sheet";
import { Text } from "@business-os/app-kit/components/text";
import { styles as ui } from "@business-os/app-kit/components/ui";
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
    <Sheet visible={visible} onClose={onClose} palette={palette} title={title} subtitle={when} closeLabel={t("close")} footer={action}>
      {coach ? <Text style={[ui.muted, { color: palette.foreground }]}>{coach}</Text> : null}
      {place ? <Text style={[ui.muted, { color: palette.muted }]}>{place}</Text> : null}
      {description ? (
        <>
          <Text style={[ui.h2, { color: palette.foreground }]}>{t("aboutClass")}</Text>
          <Text style={[ui.muted, { color: palette.foreground }]}>{description}</Text>
        </>
      ) : null}
      {social && <SessionFriends sessionId={sessionId} alwaysOpen canInviteFriends={booked} onLeave={onClose} />}
    </Sheet>
  );
}
