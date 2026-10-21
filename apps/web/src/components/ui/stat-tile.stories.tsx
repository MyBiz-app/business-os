import type { Meta, StoryObj } from "@storybook/nextjs-vite";

import { StatTile } from "./stat-tile";

const meta: Meta = { title: "Components/StatTile", component: StatTile };
export default meta;
type Story = StoryObj;

export const Row: Story = {
  render: () => (
    <div className="grid max-w-4xl grid-cols-2 gap-3 lg:grid-cols-4">
      <StatTile label="Revenue" value="$12,480" trend={{ direction: "up", label: "+12%", tone: "good" }} hint="vs last month" />
      <StatTile label="Active clients" value="318" trend={{ direction: "flat", label: "No change" }} />
      <StatTile label="Cancellations" value="9" trend={{ direction: "down", label: "-3", tone: "good" }} />
      <StatTile label="New leads" value="41" href="/leads" trend={{ direction: "down", label: "-8%", tone: "bad" }} />
    </div>
  ),
};

export const Active: Story = { args: { label: "Open invoices", value: "7", href: "/invoices", active: true } };
