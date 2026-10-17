import { ServiceEditor } from "../../../services/service-editor";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ServiceEditor id={id} modal={true} />;
}
