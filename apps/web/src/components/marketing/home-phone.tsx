import { getTranslations } from "next-intl/server";
import { HomePhoneStage, type HomePhoneLabels } from "@/components/marketing/home-phone-stage";

/** The home page phone: a CSS 3D app that tilts toward the pointer and the scroll, and rotates
 * through the schedule, friends and invite screens. Texts come from `marketing.app.phone`. */
export async function HomePhone() {
  const t = await getTranslations("marketing");
  const labels: HomePhoneLabels = {
    title: t("app.phone.title"),
    days: t.raw("app.phone.days") as string[],
    classes: t.raw("app.phone.classes") as string[],
    friendsTitle: t("app.phone.friendsTitle"),
    friends: t.raw("app.phone.friends") as string[],
    friendsNote: t("app.phone.friendsNote"),
    inviteTitle: t("app.phone.inviteTitle"),
    inviteClass: t("app.phone.inviteClass"),
    inviteFriend: t("app.phone.inviteFriend"),
    inviteCta: t("app.phone.inviteCta"),
    inviteSent: t("app.phone.inviteSent"),
  };
  return <HomePhoneStage labels={labels} />;
}
