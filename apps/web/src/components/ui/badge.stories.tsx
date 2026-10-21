import type { Meta, StoryObj } from "@storybook/nextjs-vite";

import { Badge, StatusDot } from "./badge";

const meta: Meta = { title: "Components/Badge and StatusDot", component: Badge };
export default meta;
type Story = StoryObj;

export const Tones: Story = {
  render: () => (
    <div className="flex flex-wrap items-center gap-2">
      <Badge>Neutral</Badge>
      <Badge tone="primary">Primary</Badge>
      <Badge tone="success">Active</Badge>
      <Badge tone="warning">Expiring</Badge>
      <Badge tone="danger">Overdue</Badge>
      <Badge tone="info">New</Badge>
      <Badge tone="success" dot>
        With a dot
      </Badge>
    </div>
  ),
};

export const Dots: StoryObj = {
  render: () => (
    <div className="flex flex-col gap-2">
      <StatusDot tone="success" label="Active member" />
      <StatusDot tone="warning" label="Membership ends in 3 days" />
      <StatusDot tone="danger" label="Payment failed" />
      <StatusDot tone="neutral" label="Only for screen readers" hideLabel />
    </div>
  ),
};
