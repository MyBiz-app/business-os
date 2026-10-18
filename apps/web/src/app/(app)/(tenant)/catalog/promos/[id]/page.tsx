import { PromoEditor } from "../promo-editor";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <PromoEditor id={id} modal={false} />;
}
