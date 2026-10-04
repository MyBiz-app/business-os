import { useEffect, useRef, useState } from "react";
import { AccessibilityInfo, Animated, Easing, Platform, Pressable, type PressableProps, type StyleProp, type ViewStyle } from "react-native";

const native = Platform.OS !== "web";

/** Whether the user asked the system to reduce motion; animations are skipped then. */
export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    void AccessibilityInfo.isReduceMotionEnabled().then(setReduced);
    const subscription = AccessibilityInfo.addEventListener("reduceMotionChanged", setReduced);
    return () => subscription.remove();
  }, []);
  return reduced;
}

/** Fades and lifts its content in when it first appears; `index` staggers siblings. */
export function FadeIn({ children, index = 0, style }: { children: React.ReactNode; index?: number; style?: StyleProp<ViewStyle> }) {
  const reduced = useReducedMotion();
  const progress = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    Animated.timing(progress, {
      toValue: 1,
      duration: reduced ? 0 : 420,
      delay: reduced ? 0 : Math.min(index, 6) * 60,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: native,
    }).start();
  }, [progress, index, reduced]);
  return (
    <Animated.View
      style={[
        style,
        {
          opacity: progress,
          transform: [{ translateY: progress.interpolate({ inputRange: [0, 1], outputRange: [12, 0] }) }],
        },
      ]}
    >
      {children}
    </Animated.View>
  );
}

/** A pressable that shrinks slightly while pressed, for tactile feedback. */
export function PressableScale({ style, children, ...props }: PressableProps & { style?: StyleProp<ViewStyle>; children: React.ReactNode }) {
  const reduced = useReducedMotion();
  const scale = useRef(new Animated.Value(1)).current;
  const to = (value: number) =>
    Animated.spring(scale, { toValue: value, speed: 40, bounciness: 6, useNativeDriver: native }).start();
  return (
    <Pressable
      {...props}
      onPressIn={(event) => {
        if (!reduced) to(0.97);
        props.onPressIn?.(event);
      }}
      onPressOut={(event) => {
        to(1);
        props.onPressOut?.(event);
      }}
    >
      <Animated.View style={[style, { transform: [{ scale }] }]}>{children}</Animated.View>
    </Pressable>
  );
}
