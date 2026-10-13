import type { TextProps } from "react-native";

import { Text } from "./text";

// Left-to-right isolate: the characters inside keep their order no matter what surrounds them.
const LRI = "⁦";
const PDI = "⁩";

/** A string of Latin letters or digits (phone, email, price, code) as a left-to-right run inside Hebrew text. */
export function ltr(value: string): string {
  return `${LRI}${value}${PDI}`;
}

/** `<Ltr>+972 50 123 4567</Ltr>`: the same, as a Text. It reads left to right and does not jump around inside RTL lines. */
export function Ltr({ children, style, ...props }: TextProps) {
  return (
    <Text {...props} style={[{ writingDirection: "ltr" }, style]}>
      {children}
    </Text>
  );
}
