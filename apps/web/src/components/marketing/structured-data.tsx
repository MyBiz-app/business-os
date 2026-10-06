import { getLocale, getTranslations } from "next-intl/server";

import { siteOrigin } from "@/lib/origin";

/** Structured data (schema.org), so a search result can show the product, its price and the
 * questions it answers. Everything here comes from the same translations the pages render, so
 * the markup can never say something the page does not. */
function JsonLd({ data }: { data: object }) {
  return (
    <script
      type="application/ld+json"
      // The data is ours (translations and the price list), never user input.
      dangerouslySetInnerHTML={{ __html: JSON.stringify(data).replace(/</g, "\\u003c") }}
    />
  );
}

/** The product itself, on the home page. */
export async function OrganizationData({ price, currency }: { price?: number; currency?: string }) {
  const t = await getTranslations("app");
  const origin = await siteOrigin();
  const locale = await getLocale();
  return (
    <JsonLd
      data={{
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        name: t("name"),
        description: t("tagline"),
        url: origin,
        applicationCategory: "BusinessApplication",
        operatingSystem: "Web, iOS, Android",
        inLanguage: locale,
        publisher: { "@type": "Organization", name: t("name"), url: origin },
        ...(price !== undefined && currency
          ? {
              offers: {
                "@type": "Offer",
                price,
                priceCurrency: currency,
                url: `${origin}/pricing`,
                availability: "https://schema.org/InStock",
              },
            }
          : {}),
      }}
    />
  );
}

/** The questions a page already answers, from the same list it renders. */
export async function FaqData() {
  const t = await getTranslations("marketing.faq");
  const items = t.raw("items") as { q: string; a: string }[];
  return (
    <JsonLd
      data={{
        "@context": "https://schema.org",
        "@type": "FAQPage",
        mainEntity: items.map((item) => ({
          "@type": "Question",
          name: item.q,
          acceptedAnswer: { "@type": "Answer", text: item.a },
        })),
      }}
    />
  );
}
