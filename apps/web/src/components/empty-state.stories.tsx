import type { Meta, StoryObj } from "@storybook/nextjs-vite";

import { EmptyState } from "./empty-state";
import { Button } from "./ui/button";

const meta: Meta = { title: "Components/EmptyState", component: EmptyState };
export default meta;
type Story = StoryObj;

export const WithAction: Story = {
  render: () => (
    <EmptyState variant="people" title="No clients yet" action={<Button variant="primary">Add the first client</Button>}>
      Clients appear here when they sign up with your join code or when you add them.
    </EmptyState>
  ),
};

export const Variants: Story = {
  render: () => (
    <div className="grid max-w-4xl gap-4 sm:grid-cols-2">
      <EmptyState variant="calendar">Nothing scheduled today.</EmptyState>
      <EmptyState variant="chart">Not enough data for this period.</EmptyState>
      <EmptyState variant="inbox">You are all caught up.</EmptyState>
      <EmptyState variant="list">No results for this filter.</EmptyState>
    </div>
  ),
};
