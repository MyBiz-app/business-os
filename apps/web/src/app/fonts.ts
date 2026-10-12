import { Heebo, Plus_Jakarta_Sans } from "next/font/google";

/** The site's one font. To change it, swap the import and the call below for another
 * next/font/google font that has Hebrew and Latin (e.g. Rubik, Assistant, Noto Sans Hebrew);
 * everything else picks it up through the --font-main CSS variable. */
export const mainFont = Heebo({
  variable: "--font-main",
  subsets: ["hebrew", "latin"],
});

/** The marketing site's display face for Latin text (headings, numbers, English copy). Hebrew
 * falls through to the main font, so both languages share one rhythm. */
export const displayFont = Plus_Jakarta_Sans({
  variable: "--font-display",
  subsets: ["latin"],
});
