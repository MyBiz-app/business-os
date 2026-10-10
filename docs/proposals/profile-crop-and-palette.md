# Profile: picture cropping and personal colors

Part of the workspace upgrade ([crm-upgrade-2026-10.md](crm-upgrade-2026-10.md)), from the owner's
follow-up of 2026-10-10. Two slices, one pull request each.

## 1. Cropping pictures (profile picture and business logo)

**Before:** the chosen file is uploaded as it is; a wide or off-center photo ends up badly framed
in the round avatar.

**Now:** choosing a file opens a dialog with a square window over the picture and a circle that
shows how it will look everywhere (avatars and the logo are round). The person drags the picture,
zooms with a slider, the mouse wheel or the buttons, and uses the arrow keys and `+`/`-` from the
keyboard. "Use this picture" saves the visible square.

- The crop happens in the browser (canvas), so the API and the database do not change. The saved
  picture is a square WebP of up to 512 px (transparent corners of a PNG logo are kept); quality
  or size is lowered until it fits the 512 KB the API accepts.
- The same dialog serves the profile picture (`account`) and the business logo (`settings`).
- The math (cover scale, clamping, the source square) is in `lib/image-crop.ts` with unit tests.

## 2. Personal colors

**Before:** three fixed palettes (MyBiz, Ocean, Forest), X25.

**Now:** a fourth choice, **My own colors**: the person picks three colors, and the whole app is
styled with them. The three presets stay.

| Pick | Used for |
|---|---|
| Background | the page canvas; its lightness decides whether the app is light or dark |
| Text | headings and body text |
| Accent | buttons, links, highlights |

Colors can never clash or hide parts of the app, because the input is never used as typed. The
rest of the tokens are **derived** (`lib/palette-colors.ts`, unit-tested) and each is pushed to
a readable value:

- text reaches contrast 7:1 on the background; secondary text 4.5:1;
- the accent reaches 4.5:1 on the background and on cards (so a link or button edge is always
  visible); the text on a button is black or white, whichever reads better;
- cards, borders and hover surfaces are mixed from background and text, so they are always
  distinct from the page; success / warning / danger keep their meaning and are pushed to 4.5:1;
- the app's light/dark mode follows the background's lightness (the light/dark switch is
  disabled while own colors are active, with an explanation);
- the editor shows a live preview and says "we adjusted the text color so it stays readable"
  when it had to change something. All black, or the same color three times, still gives a
  usable screen.

Storage: three columns on `app.users` (`palette_background`, `palette_text`, `palette_accent`,
`#rrggbb`) next to `palette`, which gains the value `custom`. The colors are kept when the person
switches to a preset, so switching back is one click. The API validates the format only; the
guard is the derivation, which runs in the browser from the saved colors and from a local copy
(no flash on the next page load).

A business's own brand color (X25) still colors its area on top of the person's palette.
