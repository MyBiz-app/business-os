/** How far a scroll view must move up so a field that has focus ends up above the keyboard.
 *
 * `inputBottom` and `keyboardTop` are window coordinates (the bottom edge of the field and the top
 * edge of the keyboard); `margin` is the breathing room kept between them. Zero when the field is
 * already visible: the screen never scrolls for nothing. */
export function revealDelta({ inputBottom, keyboardTop, margin }: { inputBottom: number; keyboardTop: number; margin: number }): number {
  return Math.max(0, Math.round(inputBottom + margin - keyboardTop));
}

/** The height the keyboard covers, from the top edge it reports and the window height. */
export function coveredHeight(keyboardTop: number, windowHeight: number): number {
  return Math.max(0, Math.round(windowHeight - keyboardTop));
}
