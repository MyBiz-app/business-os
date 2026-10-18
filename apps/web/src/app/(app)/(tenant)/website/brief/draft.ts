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
