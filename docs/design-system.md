# Design system and "where to change what"

Every look-and-feel decision lives in **one place**, so a change like "switch the site's font"
or "make the brand purple" touches one file and nothing else. If you find yourself editing the
same value in several files, it should become a token here first.

## Quick map

| I want to change… | Edit | Notes |
|---|---|---|
| The product's name ("MyBiz" for now, X21) | `packages/i18n/brand.json` | Translations write "MyBiz" and every app swaps it for this name (`@business-os/i18n/brand`); then `pnpm --filter @business-os/i18n export:api` for the API's copy. The store names live in each Expo app's `app.json` (`expo.name`). The logo and icons are separate assets. |
| The website's font | `apps/web/src/app/fonts.ts` | Swap `Heebo` for another `next/font/google` font with Hebrew + Latin (Rubik, Assistant, Noto Sans Hebrew…). Exposed as `--font-main`. |
| UI colors (page, cards, text, borders, success/danger/warning) | `apps/web/src/app/globals.css` → `:root` (light) and `.dark` (dark) | Components use only these tokens (`bg-surface`, `text-muted`, `border-border`…), never raw hex. |
| The default accent (buttons, links, focus) | `--primary` / `--on-primary` in `globals.css` | A business's own brand color overrides it inside its pages (`.brand`, set by `lib/brand.ts`). |
| MyBiz's brand gradient (logo tile, hero accent, call-to-action band, badges) | `--brand-from`, `--brand-via`, `--brand-to`, `--brand-strong-*`, `--brand-ink` in `globals.css` | Used as `from-brand-from to-brand-to`. |
| The MyBiz logo (mark, wordmark, favicon, app icons) and its colors | `packages/brand/src/index.ts` | Then `pnpm --filter @business-os/brand build:assets` redraws every logo file (web favicon, the three apps' icons, the SVGs in `packages/brand/assets`); run it after a name change too, for the wordmark. The web header draws the mark from the same values (`components/brand-mark.tsx`). |
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
2. **Logical direction.** `ms-*`, `ps-*`, `start-*`, `text-start` — never left/right — so
   Hebrew (RTL) and English (LTR) share the same code.
3. **Both themes.** Every token has a light and a dark value; check both before merging.
4. **Shared building blocks.** A pattern used twice becomes a component or a `@utility`
   (web) or moves to `packages/app-kit` (apps).
5. **Data-driven variety.** Industries and modules are catalog entries, not `if` branches.
