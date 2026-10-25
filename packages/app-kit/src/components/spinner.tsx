import { ActivityIndicator, type ActivityIndicatorProps } from "react-native";
import { useTranslations } from "use-intl";

/** The loading spinner with a spoken name: on the web it is a progress bar, which needs one. */
export function Spinner(props: ActivityIndicatorProps) {
  const t = useTranslations("common");
  return <ActivityIndicator accessibilityLabel={t("loading")} {...props} />;
}
