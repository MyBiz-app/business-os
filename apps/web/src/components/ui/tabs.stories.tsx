import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { useState } from "react";

import { TabPanel, Tabs } from "./tabs";

const meta: Meta = { title: "Components/Tabs", component: Tabs };
export default meta;
type Story = StoryObj;

const ITEMS = [
  { value: "overview", label: "Overview" },
  { value: "billing", label: "Subscriptions and payments", badge: 2 },
  { value: "visits", label: "Visits" },
  { value: "activity", label: "Activity" },
];

function InPage() {
  const [value, setValue] = useState("overview");
  return (
    <div className="max-w-2xl">
      <Tabs label="Client sections" idPrefix="client" items={ITEMS} value={value} onChange={setValue} />
      {ITEMS.map((item) => (
        <TabPanel key={item.value} idPrefix="client" value={item.value} active={item.value === value} className="py-4 text-sm">
          Content of {item.label}. Arrow keys, Home and End move between the tabs.
        </TabPanel>
      ))}
    </div>
  );
}

export const SameContentArea: Story = { render: () => <InPage /> };

export const OneAddressPerTab: Story = {
  render: () => (
    <div className="max-w-2xl">
      <Tabs label="Team sections" value="schedule" items={[
        { value: "people", label: "People", href: "/team" },
        { value: "schedule", label: "Schedule", href: "/team/schedule" },
        { value: "time", label: "Time clock", href: "/team/time" },
      ]} />
    </div>
  ),
};
