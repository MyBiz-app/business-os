# Design system and "where to change what"

Every look-and-feel decision lives in **one place**, so a change like "switch the site's font"
or "make the brand purple" touches one file and nothing else. If you find yourself editing the
same value in several files, it should become a token here first.

## Quick map

| I want to change… | Edit | Notes |
|---|---|---|
| The product's name ("MyBiz" for now, X21) and every other place it appears: domain, emails, app scheme, company details | `packages/i18n/brand.json` | Translations write "MyBiz" and every app swaps it for this name (`@business-os/i18n/brand`). `pnpm brand:sync` copies the file to the API, Supabase config and templates and the Expo config; see [`brand-rename.md`](brand-rename.md). The logo and icons are separate assets. |
| The website's font | `apps/web/src/app/fonts.ts` | Assistant (Hebrew + Latin) is the body font, exposed as `--font-main`; Latin headings (h1-h3, `.font-display`) use Plus Jakarta Sans. To swap, change the import in `fonts.ts` and the two files in `app/(marketing)/fonts/` used by the share image. |
| Page width, gutters, section bands, page heading | `components/layout/` (`Container`, `Section`, `PageHeader`) and the `page-gutter`, `section-y*` utilities in `globals.css` | Containers cap at 1440px (`wide`), CRM uses `size="full"`. Bands (`Section`) reach the screen edges. |
| Mixed Hebrew/English text | `components/bidi.tsx` (`Ltr`, `UserText`, `brandText`, `DIRECTIONAL_ICON`), `lib/bidi.ts` (`inputDir`) | Emails, phones, URLs, prices go in `<Ltr>`; user-typed text in `<UserText>`; the lint rule `direction/no-physical-classes` forbids `ml-`, `left-`, `text-left` and similar. |
| Light/dark one-click button | `components/theme-toggle.tsx` (`ThemeToggle`) | For the marketing header/footer and the CRM top bar. The three-way choice stays in `ThemeSwitcher`. |
| Screenshots of every screen (he/en, light/dark, 390/1440/1920) | `e2e/screen_sweep.py` | Also flags pages that scroll sideways. |
| UI colors (page, cards, text, borders, success/danger/warning, soft status tints) | `apps/web/src/app/globals.css` → `:root` (light) and `.dark` (dark) | The Calm palette (see below). Components use only these tokens (`bg-surface`, `bg-subtle`, `text-muted`, `border-border`, `bg-success-soft`…), never raw hex. |
| The product's type scale, weights and corners (business app and console) | `.app-shell` block in `globals.css` | Remaps Tailwind's `text-*`, `font-bold`/`font-extrabold` and `rounded-2xl`/`rounded-3xl` to Calm, so pages follow without editing their classes. The marketing site (`.mk`) keeps its own scale. |
| The default accent (buttons, links, focus) | `--primary` / `--on-primary` in `globals.css` | A business's own brand color overrides it inside its pages (`.brand`, set by `lib/brand.ts`). |
| MyBiz's brand gradient (logo tile, hero accent, call-to-action band, badges) | `--brand-from`, `--brand-via`, `--brand-to`, `--brand-strong-*`, `--brand-ink` in `globals.css` | Used as `from-brand-from to-brand-to`. |
| The MyBiz logo (mark, wordmark, favicon, app icons) and its colors | `packages/brand/src/index.ts` | Then `pnpm --filter @business-os/brand build:assets` redraws every logo file (web favicon, the three apps' icons, the SVGs in `packages/brand/assets`); run it after a name change too, for the wordmark. The web header draws the mark from the same values (`components/brand-mark.tsx`). |
| The color palettes a person picks (MyBiz, Ocean, Forest, X25) | `[data-palette=…]` blocks (light and `.dark`) in `globals.css`, the list in `apps/web/src/components/palette.tsx` | `--palette-primary` / `--palette-on-primary` feed `--primary`; a business's brand color still wins inside its area. A new palette: add its CSS block, its entry in `PALETTES`, its name in the translations and in the API's allowed values (`users.palette` check). |
| Branch colors (calendar, switcher, branch comparison) | `BRANCH_COLORS` in `apps/web/src/lib/calendar.ts` | A branch keeps its color by its place in the branch list. |
| Shadows, motion easing | `--elevation*`, `--ease-out` in `globals.css` | |
| See or try a component (light/dark, left-to-right/right-to-left) | `pnpm --filter web storybook` (port 6006), stories next to each component as `*.stories.tsx`; `.storybook/` | Free, no Chromatic: before/after screenshots of whole pages stay in `e2e/screen_sweep.py`. A new shared component comes with a story. |
| Buttons, cards, inputs, entrance animations | `@utility btn-primary`, `btn-secondary`, `card`, `card-accent`, `control`, `enter`… in `globals.css` | Pages use these utilities, so restyling a button restyles every button. |
| Add-on icons and colors | `apps/web/src/components/modules/module-icon.tsx` | One entry per module; used by pricing, sign-up and cart. |
| Industry icons, colors, services, plans, client fields | `packages/verticals/catalog/*.json` | Then `pnpm verticals:export`. See [verticals.md](verticals.md). |
| Any text the user sees (Hebrew / English) | `packages/i18n/messages/he.json`, `en.json` | No text is hard-coded in components. |
| Module prices and presets | `apps/api/app/commerce/modules.py` | The pricing page and sign-up read them from the API. |
| Marketing page sections (hero, features, branches, safety, FAQ, CTA) | `apps/web/src/components/marketing/sections.tsx` and the page files under `app/(marketing)/` | Each section is a component; pages compose them. |
| Mobile app's colors, corners, type scale and spacing | `packages/design-tokens/src/index.ts` (re-exported by `packages/app-kit/src/lib/theme.ts`) | The Expo app is one app (clients, business, MyBiz team). The palette is the web's Calm palette; `packages/design-tokens/test` compares it with `globals.css`, so change both together. |

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
| `--primary-ink` / `text-primary-ink` | `primaryInk` | Links, eyebrows, the current menu item, text on `bg-primary-subtle` | #1D4ED8 | #60A5FA |
| `--on-primary` / `text-on-primary` | `onPrimary` | Text on a `bg-primary` fill (white on the night blue is only 3.7:1, so night uses charcoal) | #FFFFFF | #111113 |
| `--success` / `bg-success` | `success` | Dots, bars, fills | #16A34A | #22C55E |
| `--success-ink` / `text-success-ink` | `successInk` | Check marks, deltas, "paid" text | #15803D | #4ADE80 |
| `--on-danger` / `text-on-danger` | `onDanger` | Text on a `bg-danger` fill (white in light, charcoal in dark: the dark red is too light for white) | #FFFFFF | #111113 |
| `--muted` / `text-muted` | `muted` | Secondary text (4.5:1 even on a 12% primary tint) | #63636E | #A1A1AA |

Never write `text-primary` or `text-success` for text: the bright colors are 3.3 to 4.4:1 on white
and on their own tint. A business's brand color is already made AA-safe by `lib/brand.ts`
(web) and `packages/app-kit/src/lib/brand.ts` (apps): it must reach 4.5:1 on the surface, on a
12% tint of itself, and for the text placed on it. Inside `.brand`, `--primary-ink` is that color.

## Calm (spec v4, design round W2-2)

The product's visual language, taken from the Figma "Calm" foundations (file `6NKFPYTT2pkLQz1CIxFpVN`,
page Foundations). Quiet: hierarchy by size, not weight; hairlines instead of heavy frames; one action color.

| | Light | Dark | Token |
|---|---|---|---|
| Page | #F7F7F8 | #111113 | `--background` |
| Surface (cards, menus, top bar) | #FFFFFF | #1A1A1D | `--surface` |
| Subtle fill (table header, hover, tracks) | #F2F2F4 | #232327 | `--subtle` / `bg-subtle` |
| Current item, selected row | 8% primary | 16% primary | `--primary-subtle` / `bg-primary-subtle` |
| Border | #E6E6EA | #2E2E33 | `--border` |
| Text / muted | #18181B / #63636E | #F4F4F5 / #A1A1AA | `--foreground` / `--muted` |
| Status tints (background) | #ECFDF3, #FFF7E6, #FEF2F2, #EFF6FF | #12261A, #2A2010, #2A1414, #14203A | `bg-success-soft`, `bg-warning-soft`, `bg-danger-soft`, `bg-info-soft` (text: the matching `-ink`, `text-warning`, `text-danger`, `text-info-ink`) |

- **Type** (business app and console, Assistant): 12 caption, 13 small (`text-sm`), 15 body (the default and
  `text-base`), 17 subheading (`text-lg`), 20 heading (`text-xl`), 24 title (`text-2xl`, page titles), 30 display
  (`text-3xl`; `text-4xl` caps here too). Weights 400 and 600 only: `font-bold` and `font-extrabold` render 600,
  and h1-h3 are 600 with normal letter spacing.
- **Corners**: 10px controls (`--radius-control`, buttons and fields), 12px cards (`--radius-card`, `card`,
  `rounded-2xl`), 16px windows (`--radius-dialog`, the modal, `rounded-3xl`).
- **Depth**: cards are flat (surface + hairline, `--elevation` is none); only what floats casts a shadow
  (`--elevation-floating`: menus, popovers; the modal has its own). A clickable card lifts on hover (`--elevation-hover`).
- **No gradients in the product**: not on buttons, page titles or the page background. They stay on the marketing
  site, the logo, and two brand moments (the first screen after sign-up, the AI team).
- **Navigation**: the side menu and the top bar are light by default (`.nav-light`, the page's own surface); a
  person can still pick the dark (charcoal) column in light mode (`nav_tone` cookie, `.nav-dark`).
- The marketing site (`.mk`) restores its rounder cards (20px), fields (12px) and soft card shadow.

### Calm in the Expo app (W5-1)

The app speaks the same language as the web. Shared pieces (`packages/app-kit/src/components`): `Button` (primary, secondary,
danger, quiet; 44px tall, 10px corners, no glow), `Field`, `Card` (flat, hairline, no card inside a card), `Heading`,
`EmptyState` (a quiet icon, what is missing, an optional hint and action: use it instead of grey text),
`Skeleton`, `Sheet` (the one bottom sheet: scrim and sheet animate separately, Esc / back / scrim / close button all
close it), `BackBar` (a back link; without `onPress` it goes back in history or to its `fallback` route when opened
directly, so no pushed screen is a dead end). Depth: cards carry no shadow; only what floats (`elevation.floating`: sheet,
toast, the AI bubble) does.

## Components

- **React components (CRM Premium W3-1, `apps/web/src/components/ui`)**, built once on the Calm tokens; screens compose
  them and never restyle them. The text always comes in as props (nothing is translated inside a component).
  - `Button` (`primary` the one main action, `secondary` the default, `quiet` cancel/toolbar, `danger` delete, `plain` a
    card or row that is a button), `ButtonLink` (goes somewhere), `IconButton` (needs a `label`). 36px tall on a desktop,
    44px on a touch screen (the global rule in `globals.css`), `size="lg"` for a call to action, `pending` disables and
    announces busy. `type` defaults to `button`.
  - `Card` (flat surface, hairline, 16px padding on a phone and 20px on a desktop; `tone="accent"`, `interactive`) and
    `CardHeader`. No card inside a card.
  - `PageHeader` (`components/layout`, title, optional lead-in and actions), `Tabs` and `TabPanel` (underline tabs that
    glide; button tabs for one content area, or `href` items for one address per tab, never jumping the page),
    `Badge` (soft tint) and `StatusDot` (a dot with its meaning in words), `StatTile` (one number, small trend, optional link),
    `EmptyState` (`components/empty-state.tsx`, now with `title` and `action`).
  - `Popover` and `Menu`: one positioning method. The panel is a native top-layer element (`popover="manual"`), placed by
    `lib/popover-position.ts` (tested): it opens on the preferred side, flips when it does not fit, stays inside the screen
    and follows the reading direction (`bottom-start` aligns to the right edge in Hebrew). A click outside and Esc close it;
    the arrow keys move in a menu. Use these for every new menu; the older hand-made ones (`user-menu.tsx`, `more-menu.tsx`)
    move over in the page passes.
  - `RecordLayout` and `RecordHeader` (W3-5): the Record page template. The header (`components/layout/record-header.tsx`:
    picture, name, status badge, one quiet line, actions, a thin line of numbers) sits over underline tabs
    (`components/record-layout.tsx`: every tab stays mounted, `#tab` in the address opens it) with an optional `aside` column
    of fixed facts on wide screens. Clients and leads use it; staff, quotes and the like move over in their group's pass.
  - Already there, reuse: `Modal`, `ConfirmDialog`, `Sheet` (`placement="side"`), `Tour`, `SegmentedControl`, `Pill`,
    `SummaryTiles`. `DataTable` comes in W4-1.
- Buttons: `btn-primary`, `btn-secondary`, `btn-danger` (visible buttons), `btn-ghost` (quiet
  button), `btn-lg` (size). Three bare variants keep focus ring, cursor and disabled behavior
  identical when the element is not a filled button: `btn-link` (text action, underlines on hover),
  `btn-icon` (icon only; also give it an `aria-label`), `btn-plain` (a card, chip or row that is a
  button). Inputs and selects use `control`.
- Loading: every route group has a `loading.tsx` rendering `components/layout/page-skeleton.tsx`
  (auth, the business area, the platform console, and the signed-in shell). The landing site has none
  on purpose: the old page stays until the next one is ready and then the page and footer cross-fade
  once (180ms), so a click never shows a skeleton in between. Copy the
  pattern for a heavy page: a `loading.tsx` next to it with a skeleton of its shape.
- UI kit (`apps/web/src/components/ui`, round 7): `Modal` (always centered with room around it, a
  sheet on a phone, `placement="side"` for a record sheet; the page behind does not scroll; Esc, X and
  backdrop close it, `dirty` asks "Leave without saving?", buttons go in `footer`, `data-autofocus`
  on a button starts on it), `ConfirmDialog` / `useConfirm()` / `useConfirmedSubmit()` (the question
  before a delete; never `window.confirm`), the guided `Tour` (`components/tour`: one card that glides
  between centered and pointing; skipping never moves the page), `CollapsibleSection` (`variant="inline"` is a bare arrow and title for a show-all, an add form or a danger zone; a raw `<details>` is banned by a test except the two popovers; arrow at the start, state remembered with `storageKey`;
  use it instead of a bare `<details>`), `SegmentedControl` (the pill slides) with `ContentSwap`
  (old content fades out in 100ms, new fades in in 150ms), and loading states: `LoadingDots`,
  `ProgressBar`, `PendingContent` (keeps old content dimmed while new data loads, never a blank
  page or a jump to the top). Every transition is 200ms or less, never blocks an action and is off
  under "reduce motion". Styles are the `modal-*`, `section-*`, `segmented-pill`, `content-swap`,
  `loading-dots`, `progress-bar` and `pending-*` blocks at the end of `globals.css`.
- Forms as windows (R10): a form that should open over the list it came from gets a page body
  component (for example `leads/new/new-lead-body.tsx`) used by the normal page and by an
  intercepting page in `app/(app)/(tenant)/@modal/(.)leads/new/`, wrapped in `RouteModal`
  (`components/ui/route-modal.tsx`). A link to the address opens the window; a reload or a shared
  link opens the page. Put `<ModalMarker saved={state.saved} next={state.next} />` in the form and
  have its create action return `{ saved: true }` (plus `next` to open another page) instead of
  redirecting when `formData.get("_modal")` is set. Give the save row the `form-actions` class so it
  stays visible while the fields scroll. Any address without a window closes it (`@modal/[...catchAll]`).
- Toasts: `useToast()` in `components/toast/toaster.tsx` (web) and `components/toast.tsx` in
  app-kit (apps), same API: `toast("success" | "error" | "info", message, { action })`. A dark
  card in the corner at the reading start (top on a phone), several stack as a pile that opens on
  hover. Errors stay until closed; success and info fade after 5 seconds. Use `action` for
  "Undo" after a delete or archive and "View" after a create (live examples: `files/archive-button.tsx`,
  `schedule/[id]/session-status-button.tsx`; in the business app the session screen). `FormNotice` also turns the form's
  `SubmitButton` into "Saved" for a moment. Field errors stay next to the field.
- Page transitions (web, view transitions, no library): `components/ui/page-transition.tsx`.
  `PageTransition` goes in a `template.tsx` (a layout persists, so enter/exit never fire there):
  the landing site fades in with a 12px slide up (250ms) under a fixed header, the CRM only fades
  (150ms) inside its fixed side menu and header. `CardTransition name="lead-<id>"` on a list card plus
  `RouteModal transitionName="lead-<id>"` makes the card grow into its window and shrink back.
  Names must be unique on the page. The motion rules live at the end of `globals.css` and are off
  for `prefers-reduced-motion` and the accessibility widget; browsers without support just swap.
  No `next.config` flag is needed (Next.js 16 runs `<ViewTransition>` as is). Cards with a window
  today: lead, client, quote, invoice, receipt, session, service, plan, promo; a test
  (`lib/view-transitions.test.ts`) fails when a card name has no window name or the other way round.
  To give a new list this: wrap the card link in `CardTransition` and keep the page body in a shared
  `*-body.tsx`. Then either add an intercepting page under `@modal/(.)<route>/[id]` with
  `RouteModal transitionName` (only when the route has no static sibling such as `/clients/join`,
  because a dynamic intercept would also catch those), or open the window from the list page itself
  with `?open=<id>` (`lib/open-window.ts`, `RouteModal closeHref`; see `clients/client-window.tsx`).
- Where a page starts after a click: `components/navigation-scroll.tsx` (root layout, tested rules in
  `lib/navigation-scroll.ts`). A new page starts at the top in the same moment its content swaps; an
  address with `#id` glides to that section below the sticky header (also from another page: the
  component opens such links itself with `scroll: false`, so Next.js does not jump first); back and
  forward restore the old position; a window (`dialog.modal-dialog`) over a page keeps the page; a
  change of the query only is never touched. So a link between two pages needs no `scroll` prop; do
  not add `scroll={false}` to hide a jump, fix the cause. The one sticky offset is `stickyOffset()`
  in `lib/scroll-to-section.ts`. Menus mark the current item with `components/ui/glide-pill.tsx`
  (one marker that glides, 220ms, instant with reduced motion); give the menu `position: relative`
  and `isolate`, the marked item `aria-current` or `data-pill`, and no background of its own.
- Route progress bar: `components/ui/route-progress.tsx`, mounted once in the root layout. It shows
  only when a page change takes longer than 300ms. Do not add your own spinner for page changes;
  add a `loading.tsx` with a skeleton of the page's shape instead (`components/layout/page-skeletons.tsx`).
- Side menu with sub-items (R12): an area may list `children`: pages (`/catalog?tab=plans`, chosen by
  `?tab=`) or sections of the open page (`/ai#ai-team`, which scrolls smoothly and follows the scroll).
  The matching rules are in `lib/nav-match.ts` (tested): the most specific address wins, a sub-page
  wins a tie with its area, a section link needs an element with that `id` on its page. Unfolded
  state is remembered per browser.
- Skip link: every page has one `<main id="main">`. `Container as="main"` sets the id for you;
  a bare `<main>` needs `id="main"`.

## Page widths on wide screens (R15)

Checked at 390, 1440, 1920 and 2560 px. More columns, never longer lines.

| Page kind | Rule |
|---|---|
| Lists, boards, dashboard | `Container size="full"`; card grids add columns (dashboard: 6 tiles in one row from `2xl`, charts side by side). |
| Forms and settings | `Container size="settings"` (up to 1600px) plus the `form-columns` class on the page's section stack: always one column, in reading order (a two-column zigzag put open sections beside closed ones). Only small cards of equal height that never collapse use `form-grid`: one column, two once the room itself is 56rem wide (a container query, so the side menus are counted). The settings room is the `@container`. |
| Client / staff card | Content + side column; from 1920px (`min-[120rem]`) the side column becomes two columns (client card) or the overview grid gets three (staff card). |
| Long text (policies, help) | `prose`, 44rem, unchanged. |

The console follows the same rule: form-like pages (billing, team, inbox, broadcasts, AI board) are `settings`; tables and boards (overview, businesses, audit, health, integrations, website orders) are `full`. The account page is `settings` with `form-columns`. `src/lib/wide-screens.test.ts` keeps these in place and `e2e/wide_screens.py` measures them in a real browser at all four widths.

### Record card as a window (`?open=`)

The team list opens a person's card as a window over the list with `?open=<userId>` (`lib/open-window.ts`, `StaffCardWindow`), the same way clients and sessions do. The page `/team/<userId>` still exists for links and refresh and renders the same `StaffCardBody`. Each block of the card folds and remembers its state per person.

## Lint rules (CI: `pnpm turbo run lint`)

`apps/web/eslint-rules/design-system.mjs`, wired in `apps/web/eslint.config.mjs`:

- `design-system/no-raw-colors`: no hex value and no Tailwind palette class (`bg-amber-500`,
  `text-red-600`...) in `src/**`. Use tokens. Allowed only in the allow-list in `eslint.config.mjs`
  (each entry has a reason: color math, swatches, logos, product mock-ups, the hero band). Add a
  file there only for content whose color *is* the content.
- `design-system/no-scroll-jump`: a `Link` that only changes the query of its own page (period, month,
  page number, filter), or whose address a page file builds with a function, needs `scroll={false}`
  (or an explicit `scroll={true}` when the jump to the top is meant); `router.push/replace` to the
  current page passes `{ scroll: false }`. Choices that change what a page shows use
  `LinkSegmented` (`components/ui/link-segmented.tsx`): the pill slides at once, the page stays
  put and dots show while the data loads. Heavy pages have a `loading.tsx` built from
  `components/layout/page-skeletons.tsx` at the page's own `Container` width.
- `design-system/no-handrolled-ui`: new code uses `Button` / `IconButton` / `ButtonLink` instead of a bare `<button>`, and
  `DataTable` (`components/ui/data-table.tsx`) instead of a bare `<table>`. The components themselves (`components/ui/`) and stories are exempt.
  Files that predate the components are listed in `apps/web/eslint-rules/handrolled-ui-baseline.json`, a list that only
  shrinks: after moving a file over, run `node scripts/handrolled-ui-baseline.mjs` in `apps/web` (the test
  `src/lib/handrolled-ui.test.ts` fails while a listed file no longer needs its entry). A table that is not a list
  of records (a chart's data table, a printed document's line items, a calendar grid) keeps its `<table>` with
  `// eslint-disable-next-line design-system/no-handrolled-ui -- <why>`.
- `DataTable`: pass `columns` (`header`, `cell`, `align`, `nowrap`, `hideBelow`, `rowHeader`, `sortable`), `rows` and a
  `rowKey`. It has no client code, so server pages use it as is. Sorting and row selection are controlled: a
  client page uses `useDataTable` (`components/ui/use-data-table.ts`) and passes `sort`/`onSortChange`/`selection`.
  `bare` drops the card border for a table that already sits in a card. Stories: `Components/DataTable`.
- `design-system/no-raw-button`: a `<button>` needs `btn-primary`, `btn-secondary`, `btn-ghost`,
  `btn-danger`, `btn-link`, `btn-icon`, `btn-plain` or `control` in its `className`.

For the Expo app, `packages/app-kit/test/support.mjs` (run by `pnpm --filter client-app test` and `app-kit test`) fails on a
font size outside 12 / 13 / 15 / 17 / 20 / 24 / 30, a font weight of 700 or more, or a numeric corner of 8 or more: use
`radius.control` (10), `radius.card` (12), `radius.dialog` (16) or `radius.pill`, and `space` for the 4px grid, all from
`@business-os/app-kit/lib/theme`. Weights are 400 text, 500 labels, 600 headings.

For the Expo app, `no-restricted-syntax` in `apps/client-app/eslint.config.js` and
`packages/app-kit/eslint.config.js` bans hex literals outside `lib/theme.ts` and `lib/brand.ts`.
Colors that never change with theme or brand (white on a brand fill, the rating star) are
`fixedColors` in `theme.ts`. Allowed: the launch splash and the brand color swatches (their colors are the content).
