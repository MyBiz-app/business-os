import { View } from "react-native";
import { useLocale, useTranslations } from "use-intl";

import { ListRow } from "@business-os/app-kit/components/rows";
import type { Palette } from "@business-os/app-kit/lib/theme";
import { InstructorAvatar } from "@/components/instructor-avatar";
import { type Person, personName } from "@/lib/friends";

type Props = {
  person: Person;
  palette: Palette;
  onPress?: () => void;
  trailing?: React.ReactNode;
};

/** One person: round picture, name, and their status (or since when we are friends). */
export function PersonRow({ person, palette, onPress, trailing }: Props) {
  const t = useTranslations("friends");
  const locale = useLocale();
  const name = personName(person);
  const since = person.friends_since
    ? t("since", { date: new Intl.DateTimeFormat(locale, { month: "short", year: "numeric" }).format(new Date(person.friends_since)) })
    : null;
  const together = person.shared_classes > 0 ? t("together", { count: person.shared_classes }) : null;
  const subtitle = person.status_text || [since, together].filter(Boolean).join(" · ") || undefined;
  return (
    <ListRow
      palette={palette}
      title={name}
      subtitle={subtitle}
      leading={
        <View>
          <InstructorAvatar name={name} path={person.avatar_url} palette={palette} size={44} />
        </View>
      }
      trailing={trailing}
      onPress={onPress}
    />
  );
}
