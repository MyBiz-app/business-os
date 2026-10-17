# Design system and "where to change what"

Every look-and-feel decision lives in **one place**, so a change like "switch the site's font"
or "make the brand purple" touches one file and nothing else. If you find yourself editing the
same value in several files, it should become a token here first.

## Quick map

| I want to change… | Edit | Notes |
|---|---|---|
| The product's name ("MyBiz" for now, X21) | `packages/i18n/brand.json` | Translations write "MyBiz" and every app swaps it for this name (`@business-os/i18n/brand`); then `pnpm --filter @business-os/i18n export:api` for the API's copy. The store names live in each Expo app's `app.json` (`expo.name`). The logo and icons are separate assets. |
| The website's font | `apps/web/src/app/fonts.ts` | Assistant (Hebrew + Latin) is the body font, exposed as `--font-main`; Latin headings (h1-h3, `.font-display`) use Plus Jakarta Sans. To swap, change the import in `fonts.ts` and the two files in `app/(marketing)/fonts/` used by the share image. |
| Page width, gutters, section bands, page heading | `components/layout/` (`Container`, `Section`, `PageHeader`) and the `page-gutter`, `section-y*` utilities in `globals.css` | Containers cap at 1440px (`wide`), CRM uses `size="full"`. Bands (`Section`) reach the screen edges. |
| Mixed Hebrew/English text | `components/bidi.tsx` (`Ltr`, `UserText`, `brandText`, `DIRECTIONAL_ICON`), `lib/bidi.ts` (`inputDir`) | Emails, phones, URLs, prices go in `<Ltr>`; user-typed text in `<UserText>`; the lint rule `direction/no-physical-classes` forbids `ml-`, `left-`, `text-left` and similar. |
| Light/dark one-click button | `components/theme-toggle.tsx` (`ThemeToggle`) | For the marketing header/footer and the CRM top bar. The three-way choice stays in `ThemeSwitcher`. |
| Screenshots of every screen (he/en, light/dark, 390/1440/1920) | `e2e/screen_sweep.py` | Also flags pages that scroll sideways. |
| UI colors (page, cards, text, borders, success/danger/warning) | `apps/web/src/app/globals.css` → `:root` (light) and `.dark` (dark) | Components use only these tokens (`bg-surface`, `text-muted`, `border-border`…), never raw hex. |
| The default accent (buttons, links, focus) | `--primary` / `--on-primary` in `globals.css` | A business's own brand color overrides it inside its pages (`.brand`, set by `lib/brand.ts`). |
| MyBiz's brand gradient (logo tile, hero accent, call-to-action band, badges) | `--brand-from`, `--brand-via`, `--brand-to`, `--brand-strong-*`, `--brand-ink` in `globals.css` | Used as `from-brand-from to-brand-to`. |
| The MyBiz logo (mark, wordmark, favicon, app icons) and its colors | `packages/brand/src/index.ts` | Then `pnpm --filter @business-os/brand build:assets` redraws every logo file (web favicon, the three apps' icons, the SVGs in `packages/brand/assets`); run it after a name change too, for the wordmark. The web header draws the mark from the same values (`components/brand-mark.tsx`). |
| The color palettes a person picks (MyBiz, Ocean, Forest, X25) | `[data-palette=…]` blocks (light and `.dark`) in `globals.css`, the list in `apps/web/src/components/palette.tsx` | `--palette-primary` / `--palette-on-primary` feed `--primary`; a business's brand color still wins inside its area. A new palette: add its CSS block, its entry in `PALETTES`, its name in the translations and in the API's allowed values (`users.palette` check). |
| Branch colors (calendar, switcher, branch comparison) | `BRANCH_COLORS` in `apps/web/src/lib/calendar.ts` | A branch keeps its color by its place in the branch list. |
| Shadows, motion easing | `--elevation*`, `--ease-out` in `globals.css` | |
| Buttons, cards, inputs, entrance animations | `@utility btn-primary`, `btn-secondary`, `card`, `card-accent`, `control`, `enter`… in `globals.css` | Pages use these utilities, so restyling a button restyles every button. |
| Add-on icons and colors | `apps/web/src/components/modules/module-icon.tsx` | One entry per module; used by pricing, sign-up and cart. |
| Industry icons, colors, services, plans, client fields | `packages/verticals/catalog/*.json` | Then `pnpm verticals:export`. See [verticals.md](verticals.md). |
| Any text the user sees (Hebrew / English) | `packages/i18n/messages/he.json`, `en.json` | No text is hard-coded in components. |
| Module prices and presets | `apps/api/app/commerce/modules.py` | The pricing page and sign-up read them from the API. |
| Marketing page sections (hero, features, branches, safety, FAQ, CTA) | `apps/web/src/components/marketing/sections.tsx` and the page files under `app/(marketing)/` | Each section is a component; pages compose them. |
| Mobile apps' colors and spacing | `packages/app-kit/src/lib/theme.ts` | Shared by the client, business and team apps. |

## Rules that keep it modular

1. **Tokens, not values.** Colors, fonts, shadows and radii are CSS variables (web) or theme
   constants (apps). A component never contains a hex color or a font name.
2. **Logical direction.** `ms-*`, `ps-*`, `start-*`, `text-start` - never left/right - so
   Hebrew (RTL) and English (LTR) share the same code.
3. **Both themes.** Every token has a light and a dark value; check both before merging.
4. **Shared building blocks.** A pattern used twice becomes a component or a `@utility`
   (web) or moves to `packages/app-kit` (apps).
5. **Data-driven variety.** Industries and modules are catalog entries, not `if` branches.

## Text-safe color tokens (WCAG AA)

Fills and text have different contrast needs, so each accent has a bright fill color and an "ink"
for text. Use the ink whenever the color is text (or a thin icon) on a card, the page or a tint.

| Token (CSS / Tailwind) | App (`theme.ts`) | Use for | Light | Dark |
|---|---|---|---|---|
| `--primary` / `bg-primary` | `primary` | Fills, rings, focus outlines | #2563EB | #3B82F6 |
| `--primary-ink` / `text-primary-ink` | `primaryInk` | Links, eyebrows, text on `bg-primary/10` | #1D4ED8 | #60A5FA |
| `--success` / `bg-success` | `success` | Dots, bars, fills | #16A34A | #22C55E |
| `--success-ink` / `text-success-ink` | `successInk` | Check marks, deltas, "paid" text | #166534 | #4ADE80 |
| `--on-danger` / `text-on-danger` | `onDanger` | Text on a `bg-danger` fill (white in light, navy in dark: the dark red is too light for white) | #FFFFFF | #0B1020 |
| `--muted` / `text-muted` | `muted` | Secondary text (4.5:1 even on a 12% primary tint) | #52627A | #94A3B8 |

Never write `text-primary` or `text-success` for text: the bright colors are 3.3 to 4.4:1 on white
and on their own tint. A business's brand color is already made AA-safe by `lib/brand.ts`
(web) and `packages/app-kit/src/lib/brand.ts` (apps): it must reach 4.5:1 on the surface, on a
12% tint of itself, and for the text placed on it. Inside `.brand`, `--primary-ink` is that color.

## Components

- Buttons: `btn-primary`, `btn-secondary`, `btn-danger` (visible buttons), `btn-ghost` (quiet
  button), `btn-lg` (size). Three bare variants keep focus ring, cursor and disabled behavior
  identical when the element is not a filled button: `btn-link` (text action, underlines on hover),
  `btn-icon` (icon only; also give it an `aria-label`), `btn-plain` (a card, chip or row that is a
  button). Inputs and selects use `control`.
- Loading: every route group has a `loading.tsx` rendering `components/layout/page-skeleton.tsx`
  (marketing, auth, the business area, the platform console, and the signed-in shell). Copy the
  pattern for a heavy page: a `loading.tsx` next to it with a skeleton of its shape.
- UI kit (`apps/web/src/components/ui`, round 7): `Modal` (a near full-screen window over the page,
  a sheet on a phone; Esc, X and backdrop close it, `dirty` asks "Leave without saving?", buttons go
  in `footer`), `CollapsibleSection` (arrow at the start, state remembered with `storageKey`;
  use it instead of a bare `<details>`), `SegmentedControl` (the pill slides) with `ContentSwap`
  (old content fades out in 100ms, new fades in in 150ms), and loading states: `LoadingDots`,
  `ProgressBar`, `PendingContent` (keeps old content dimmed while new data loads, never a blank
  page or a jump to the top). Every transition is 200ms or less, never blocks an action and is off
  under "reduce motion". Styles are the `modal-*`, `section-*`, `segmented-pill`, `content-swap`,
  `loading-dots`, `progress-bar` and `pending-*` blocks at the end of `globals.css`.
- Toasts: `useToast()` in `components/toast/toaster.tsx` (web) and `components/toast.tsx` in
  app-kit (apps), same API: `toast("success" | "error" | "info", message, { action })`. A dark
  card in the corner at the reading start (top on a phone), several stack as a pile that opens on
  hover. Errors stay until closed; success and info fade after 5 seconds. Use `action` for
  "Undo" after a delete or archive and "View" after a create. `FormNotice` also turns the form's
  `SubmitButton` into "Saved" for a moment. Field errors stay next to the field.
- Skip link: every page has one `<main id="main">`. `Container as="main"` sets the id for you;
  a bare `<main>` needs `id="main"`.

## Lint rules (CI: `pnpm turbo run lint`)

`apps/web/eslint-rules/design-system.mjs`, wired in `apps/web/eslint.config.mjs`:

- `design-system/no-raw-colors`: no hex value and no Tailwind palette class (`bg-amber-500`,
  `text-red-600`...) in `src/**`. Use tokens. Allowed only in the allow-list in `eslint.config.mjs`
  (each entry has a reason: color math, swatches, logos, product mock-ups, the hero band). Add a
  file there only for content whose color *is* the content.
- `design-system/no-raw-button`: a `<button>` needs `btn-primary`, `btn-secondary`, `btn-ghost`,
  `btn-danger`, `btn-link`, `btn-icon`, `btn-plain` or `control` in its `className`.

For the Expo apps, `no-restricted-syntax` in `apps/client-app/eslint.config.js` and
`packages/app-kit/eslint.config.js` bans hex literals outside `lib/theme.ts` and `lib/brand.ts`.
Colors that never change with theme or brand (white on a brand fill, the rating star) are
`fixedColors` in `theme.ts`. Allowed: the launch splash and the brand color swatches (their colors are the content).
