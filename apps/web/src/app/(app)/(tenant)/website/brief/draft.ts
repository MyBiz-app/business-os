import type { components } from "@business-os/api-client";

type Brief = components["schemas"]["Brief"];

/** The brief with every list present, as the wizard edits it (the API fills defaults, its types mark them optional). */
export type Draft = Brief &
  Required<Pick<Brief, "goals" | "sections" | "colors" | "images" | "inspiration" | "languages" | "colors_from_brand" | "no_logo" | "no_good_photos">>;

export function normalize(brief: Brief | undefined): Draft {
  return {
    ...brief,
    goals: brief?.goals ?? [],
    sections: brief?.sections ?? [],
    colors: brief?.colors ?? [],
    images: brief?.images ?? [],
    inspiration: brief?.inspiration ?? [],
    languages: brief?.languages ?? [],
    colors_from_brand: brief?.colors_from_brand ?? true,
    no_logo: brief?.no_logo ?? false,
    no_good_photos: brief?.no_good_photos ?? false,
  };
}

/** What the business already told us, as the starting answers: only fills what is still empty. */
export function prefill(draft: Draft, tenant: { locale: string; address_city?: string | null; website_url?: string | null }): Draft {
  const host = tenant.website_url ? websiteHost(tenant.website_url) : null;
  return {
    ...draft,
    area: draft.area ?? (tenant.address_city || undefined),
    languages: draft.languages.length > 0 ? draft.languages : [tenant.locale === "he" ? "he" : "en"],
    domain: draft.domain ?? (host ? "have" : undefined),
    domain_name: draft.domain_name ?? (host ?? undefined),
  };
}

function websiteHost(url: string): string | null {
  try {
    return new URL(url.includes("://") ? url : `https://${url}`).hostname;
  } catch {
    return null;
  }
}
