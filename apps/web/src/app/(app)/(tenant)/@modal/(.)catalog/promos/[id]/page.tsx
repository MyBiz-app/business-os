import { PromoEditor } from "@/app/(app)/(tenant)/catalog/promos/promo-editor";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <PromoEditor id={id} modal={true} />;
}
