import { redirect } from "next/navigation";

/** Working hours and time off now live in the member's card. */
export default async function StaffHoursPage({ params }: PageProps<"/team/[userId]/hours">) {
  const { userId } = await params;
  redirect(`/team/${userId}?tab=availability`);
}
