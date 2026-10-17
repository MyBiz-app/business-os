import { redirect } from "next/navigation";

/** Availability now lives in the member's card. */
export default async function StaffAvailabilityPage({ params }: PageProps<"/team/[userId]/availability">) {
  const { userId } = await params;
  redirect(`/team/${userId}?tab=availability`);
}
