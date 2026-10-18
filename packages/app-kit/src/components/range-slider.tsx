import { useMemo, useRef, useState } from "react";
import { PanResponder, StyleSheet, View } from "react-native";

import type { Palette } from "../lib/theme";
import { fractionOf, moveHandle, valueAt, type Range } from "../lib/range-slider";

const THUMB = 28;

type Props = {
  value: Range;
  onChange: (next: Range) => void;
  min: number;
  max: number;
  step: number;
  /** The least distance between the two handles. */
  gap: number;
  palette: Palette;
  /** Names of the two handles for screen readers. */
  labels: { from: string; to: string };
  /** The spoken value of a handle. */
  describe: (value: number) => string;
};

/** A track with two handles to pick a range (a time window). It always reads left to right, like a clock. */
export function RangeSlider({ value, onChange, min, max, step, gap, palette, labels, describe }: Props) {
  const [width, setWidth] = useState(0);
  const latest = useRef({ value, width, onChange });
  latest.current = { value, width, onChange };
  const start = useRef(0);

  const responder = (handle: "from" | "to") =>
    PanResponder.create({
      onStartShouldSetPanResponder: () => true,
      onMoveShouldSetPanResponder: () => true,
      onPanResponderTerminationRequest: () => false,
      onPanResponderGrant: () => {
        start.current = latest.current.value[handle];
      },
      onPanResponderMove: (_, gesture) => {
        const { value: current, width: track, onChange: change } = latest.current;
        const usable = Math.max(1, track - THUMB);
        const next = valueAt(fractionOf(start.current, min, max) + gesture.dx / usable, min, max, step);
        change(moveHandle(current, handle, next, min, max, gap));
      },
    });
  // The responders read the latest props through the ref, so they are made once.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const handlers = useMemo(() => ({ from: responder("from"), to: responder("to") }), [min, max, step, gap]);

  const usable = Math.max(0, width - THUMB);
  const left = fractionOf(value.from, min, max) * usable;
  const right = fractionOf(value.to, min, max) * usable;

  const thumb = (handle: "from" | "to", offset: number) => (
    <View
      {...handlers[handle].panHandlers}
      role="slider"
      aria-label={labels[handle]}
      aria-valuemin={min}
      aria-valuemax={max}
      aria-valuenow={value[handle]}
      aria-valuetext={describe(value[handle])}
      accessible
      accessibilityActions={[{ name: "increment" }, { name: "decrement" }]}
      onAccessibilityAction={(event) => {
        const delta = event.nativeEvent.actionName === "increment" ? step : -step;
        onChange(moveHandle(value, handle, value[handle] + delta, min, max, gap));
      }}
      style={[local.thumb, { left: offset, backgroundColor: palette.surface, borderColor: palette.primary }]}
    />
  );

  return (
    <View style={local.wrap} onLayout={(event) => setWidth(event.nativeEvent.layout.width)}>
      <View style={[local.track, { backgroundColor: palette.border }]} />
      <View style={[local.fill, { left: left + THUMB / 2, width: Math.max(0, right - left), backgroundColor: palette.primary }]} />
      {thumb("from", left)}
      {thumb("to", right)}
    </View>
  );
}

const local = StyleSheet.create({
  wrap: { height: THUMB + 8, justifyContent: "center", direction: "ltr" },
  track: { position: "absolute", left: THUMB / 2, right: THUMB / 2, height: 6, borderRadius: 3 },
  fill: { position: "absolute", height: 6, borderRadius: 3 },
  thumb: { position: "absolute", width: THUMB, height: THUMB, borderRadius: THUMB / 2, borderWidth: 3, top: 4 },
});
