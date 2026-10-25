import type { Meta, StoryObj } from "@storybook/nextjs-vite";

import { DeviceFrame } from "./device-frame";

const meta = { title: "Components/DeviceFrame", component: DeviceFrame } satisfies Meta<typeof DeviceFrame>;
export default meta;
type Story = StoryObj<typeof meta>;

const Screen = ({ title }: { title: string }) => (
  <div className="flex h-full flex-col gap-2">
    <p className="text-base font-bold">{title}</p>
    <div className="rounded-xl bg-primary px-3 py-2 text-xs font-bold text-on-primary">07:00 Pilates</div>
    <div className="rounded-xl border border-border px-3 py-2 text-xs font-semibold">09:30 Strength</div>
  </div>
);

export const Phone: Story = { args: { device: "phone", children: <Screen title="Today" /> } };

export const Laptop: Story = { args: { device: "laptop", children: <Screen title="Schedule" /> } };

export const LaptopHalfOpen: Story = { args: { device: "laptop", lid: 0.5, children: <Screen title="Schedule" /> } };

export const Together: Story = {
  args: { device: "phone", children: null },
  render: () => (
    <div className="flex items-end gap-6">
      <DeviceFrame device="laptop" className="max-w-xl"><Screen title="Schedule" /></DeviceFrame>
      <DeviceFrame device="phone" className="!mx-0 !w-40"><Screen title="Today" /></DeviceFrame>
    </div>
  ),
};
