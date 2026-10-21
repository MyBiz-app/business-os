# Design audit, October 2026 (round 6, slice U6)

Audit only; the fixes are slice U7. Full report with 725 screenshots (marketing, CRM, console, client app on Expo web; Hebrew and English, light and dark, desktop and phone) is in the project folder `design-audit-2026-10/report.md`. Scored against the rubric in the round 6 spec, section 10.8.

| Area | High | Medium | Low |
|---|---|---|---|
| Cross-cutting (tokens, system) | 3 | 3 | 2 |
| Marketing site | 1 | 2 | 4 |
| CRM | 2 | 4 | 4 |
| Console | 0 | 2 | 2 |
| Client app (Expo web) | 3 | 2 | 1 |
| **All** | **9** | **13** | **13** |

## Main findings

- Contrast: `text-success` (3.29:1 on white) and `text-primary` on its own tint (4.1 to 4.5:1) fail WCAG AA. These cover the two known gaps (AI team page, content studio) and show up in the console, the app and the sign-up wizard. A business's brand color is used as text with no contrast guard (4.09:1 in dark mode on every app screen). Fix with `--success-ink` and `--primary-ink` tokens and an AA-safe brand text color.
- Layout: the content studio scrolls sideways by 252px on a phone; the app's sign-in and join screens scroll sideways (up to 348px) and the app has no max width on desktop browsers.
- App accessibility: icon-only buttons have no accessible name and interactive elements are nested on every route; the React Native `direction` style raises an error on every screen.
- Gap: no screen anywhere shows or changes the marketing consent, although broadcasts depend on it.
- Consistent already: fonts (Assistant, Plus Jakarta Sans), zero arbitrary spacing classes, a small radius set, no sideways scroll on marketing and console pages.

## Suggested split for the fixes (U7)

1. Tokens and lint: `--success-ink`, `--primary-ink`, brand color guard, no-hex and no-raw-button lint rule, `id="main"`, shared empty state and loading skeletons.
2. CRM and console: content studio phone layout, schedule contrast and truncation, AI bubble overlap, logo CSP, marketing consent toggle, console form controls.
3. Client app: auth overflow, desktop max width, accessible names, `direction` style, duplicate chip rows, consent toggle.
4. Marketing: hero tile contrast, features and start contrast, pricing carousel affordance.
