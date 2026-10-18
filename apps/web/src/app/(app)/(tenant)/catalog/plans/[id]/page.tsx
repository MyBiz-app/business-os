import { PlanEditor } from "../plan-editor";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <PlanEditor id={id} modal={false} />;
}
