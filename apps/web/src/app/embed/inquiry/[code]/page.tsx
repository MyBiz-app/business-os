import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { getApi } from "@/lib/api";
import { brandStyle } from "@/lib/brand";

import { InquiryForm } from "../../../inquiry/[code]/inquiry-form";

export const metadata: Metadata = { robots: { index: false, follow: false } };

/** The inquiry form without the page around it, for a business to show inside its own website
 * (an iframe). Inquiries arrive as new leads, like on the hosted inquiry page. */
export default async function EmbeddedInquiry({ params }: PageProps<"/embed/inquiry/[code]">) {
  const { code } = await params;
  const { data } = await (await getApi()).GET("/public/businesses/{code}", { params: { path: { code } } });
  if (!data?.inquiries) notFound();
  return (
    <main className="brand p-4" style={brandStyle(data.primary_color)}>
      <InquiryForm code={code} />
    </main>
  );
}
