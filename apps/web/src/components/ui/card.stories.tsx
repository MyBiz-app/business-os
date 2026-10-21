import type { Meta, StoryObj } from "@storybook/nextjs-vite";

import { Button } from "./button";
import { Card, CardHeader } from "./card";

const meta = { title: "Components/Card", component: Card } satisfies Meta<typeof Card>;
export default meta;
type Story = StoryObj<typeof meta>;

export const WithHeader: Story = {
  render: () => (
    <Card as="section" className="max-w-xl">
      <CardHeader title="Next lessons" description="Today, Studio Bloom" actions={<Button variant="quiet">View all</Button>} />
      <p className="text-sm text-muted">Flat surface, hairline border, 12px corners. Never put a card inside a card.</p>
    </Card>
  ),
};

export const Tones: Story = {
  render: () => (
    <div className="grid max-w-3xl gap-4 sm:grid-cols-2">
      <Card>Default</Card>
      <Card tone="accent">Accent: the one tinted surface of a view</Card>
      <Card interactive>Interactive: lifts on hover</Card>
      <Card padding="none">
        <p className="p-4">No padding: the content brings its own</p>
      </Card>
    </div>
  ),
};
