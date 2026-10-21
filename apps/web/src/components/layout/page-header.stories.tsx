import type { Meta, StoryObj } from "@storybook/nextjs-vite";

import { Button } from "@/components/ui/button";

import { PageHeader } from "./page-header";

const meta: Meta = { title: "Components/PageHeader", component: PageHeader };
export default meta;
type Story = StoryObj;

export const Default: Story = {
  render: () => (
    <PageHeader
      title="Clients"
      description="Everyone who trains with you, with their membership and visits."
      actions={
        <>
          <Button>Import</Button>
          <Button variant="primary">New client</Button>
        </>
      }
    />
  ),
};

export const WithEyebrow: Story = { args: { eyebrow: "Studio Bloom", title: "Today" } };
