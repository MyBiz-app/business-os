import { redirect } from "next/navigation";

/** The payroll file now lives in the member's card. */
export default async function PayrollFilePage({ params }: PageProps<"/team/[userId]/payroll">) {
  const { userId } = await params;
  redirect(`/team/${userId}?tab=employment`);
}
