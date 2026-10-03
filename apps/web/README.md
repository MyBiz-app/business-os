# web

Business web app (Next.js App Router). See the root [README](../../README.md) to run it.

- Translations: `messages/{he,en}.json`. Every user-facing string lives there.
- Locale: cookie `NEXT_LOCALE`, then browser language, then `he`. See `src/i18n/`.
- Styling: Tailwind with design tokens in `src/app/globals.css`. Use logical utilities
  (`ms-*`, `pe-*`, `start-*`, `text-start`) so RTL and LTR both work.
