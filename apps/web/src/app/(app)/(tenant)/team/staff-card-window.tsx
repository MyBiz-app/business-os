import { notFound } from "next/navigation";

import { RouteModal } from "@/components/ui/route-modal";
import { unwrap } from "@/lib/api";
import { getTenantFor } from "@/lib/tenant";

import { StaffCardBody } from "./[userId]/staff-card-body";

/** A team member's card opened as a window over the team list (`/team?open=<id>`); the tabs inside
 * keep the window open (`&tab=`). */
export async function StaffCardWindow({ id, tab, closeHref, tabBase }: { id: string; tab?: string | string[]; closeHref: string; tabBase: string }) {
  const { api, scope } = await getTenantFor("staff.manage");
  const team = unwrap(await api.GET("/staff", { params: scope }));
  const member = team.members.find((m) => m.user_id === id);
  if (!member) notFound();
  return (
    <RouteModal title={member.full_name ?? member.email} transitionName={`member-${id}`} closeHref={closeHref}>
      <StaffCardBody userId={id} tab={tab} tabBase={tabBase} />
    </RouteModal>
  );
}
