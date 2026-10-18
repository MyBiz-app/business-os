import { PlanEditor } from "@/app/(app)/(tenant)/catalog/plans/plan-editor";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <PlanEditor id={id} modal={true} />;
}
