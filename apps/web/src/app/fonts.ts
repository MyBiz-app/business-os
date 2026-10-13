import { Assistant, Plus_Jakarta_Sans } from "next/font/google";

/** The site's one font. To change it, swap the import and the call below for another
 * next/font/google font that has Hebrew and Latin (e.g. Rubik, Heebo, Noto Sans Hebrew);
 * everything else picks it up through the --font-main CSS variable. */
export const mainFont = Assistant({
  variable: "--font-main",
  subsets: ["hebrew", "latin"],
});

/** The display face for Latin headings (h1-h3 and `.font-display`). Body text and Hebrew use the
 * main font, so both languages share one rhythm. */
export const displayFont = Plus_Jakarta_Sans({
  variable: "--font-display",
  subsets: ["latin"],
});
