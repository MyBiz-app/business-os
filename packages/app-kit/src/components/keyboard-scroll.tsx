import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { Dimensions, Keyboard, Platform, TextInput, type NativeScrollEvent, type NativeSyntheticEvent, type ScrollViewInstance } from "react-native";

import { coveredHeight, revealDelta } from "../lib/keyboard";

const ios = Platform.OS === "ios";
const MARGIN = 28;

type FocusedInput = { measureInWindow: (callback: (x: number, y: number, width: number, height: number) => void) => void };

const RevealContext = createContext<(() => void) | null>(null);

/** Provided around a scroll view's content: a field calls it when it gets focus. */
export const RevealProvider = RevealContext.Provider;

/** What a field calls when it gets focus, so a screen that scrolls can bring it above the keyboard. */
export function useRevealFocused(): (() => void) | null {
  return useContext(RevealContext);
}

/** Keeps the field being typed in above the keyboard (on iPhone; Android resizes the window by
 * itself and the web has no on-screen keyboard).
 *
 * Give the scroll view `scrollRef`, spread `scrollProps` on it, add `bottomPadding` below its
 * content, and wrap the content in `<RevealProvider value={reveal}>` so fields report focus. The
 * scroll view's own `automaticallyAdjustKeyboardInsets` is not enough: it leaves a centered form
 * under the keyboard in Expo Go. */
export function useKeyboardReveal() {
  const scrollRef = useRef<ScrollViewInstance | null>(null);
  const offset = useRef(0);
  const keyboardTop = useRef<number | null>(null);
  const [bottomPadding, setBottomPadding] = useState(0);

  const reveal = useCallback(() => {
    if (!ios || keyboardTop.current === null) return;
    const top = keyboardTop.current;
    // The field takes focus a moment after its event; wait for it to be the focused one.
    setTimeout(() => {
      const input = (TextInput as unknown as { State: { currentlyFocusedInput?: () => FocusedInput | null } }).State.currentlyFocusedInput?.();
      input?.measureInWindow((_x, y, _width, height) => {
        const delta = revealDelta({ inputBottom: y + height, keyboardTop: top, margin: MARGIN });
        if (delta <= 0) return;
        offset.current += delta;
        scrollRef.current?.scrollTo({ y: offset.current, animated: true });
      });
    }, 60);
  }, []);

  useEffect(() => {
    if (!ios) return;
    const change = Keyboard.addListener("keyboardWillChangeFrame", (event) => {
      keyboardTop.current = event.endCoordinates.screenY;
      setBottomPadding(coveredHeight(event.endCoordinates.screenY, Dimensions.get("window").height));
      reveal();
    });
    const hide = Keyboard.addListener("keyboardWillHide", () => {
      keyboardTop.current = null;
      setBottomPadding(0);
    });
    return () => {
      change.remove();
      hide.remove();
    };
  }, [reveal]);

  // Where the person left the scroll view: read when a drag or a fling ends, not on every frame.
  const remember = useCallback((event: NativeSyntheticEvent<NativeScrollEvent>) => {
    offset.current = event.nativeEvent.contentOffset.y;
  }, []);

  return {
    scrollRef,
    bottomPadding,
    reveal,
    scrollProps: { onScrollEndDrag: remember, onMomentumScrollEnd: remember },
  };
}
