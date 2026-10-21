import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { Plus, Trash2 } from "lucide-react";

import { Button, ButtonLink, IconButton } from "./button";

const meta = { title: "Components/Button", component: Button, args: { children: "Save changes" } } satisfies Meta<typeof Button>;
export default meta;
type Story = StoryObj<typeof meta>;

export const Variants: Story = {
  render: (args) => (
    <div className="flex flex-wrap items-center gap-3">
      <Button {...args} variant="primary" />
      <Button {...args} variant="secondary" />
      <Button {...args} variant="quiet" />
      <Button {...args} variant="danger">
        Delete
      </Button>
    </div>
  ),
};

export const WithIcon: Story = {
  render: () => (
    <div className="flex flex-wrap items-center gap-3">
      <Button variant="primary">
        <Plus aria-hidden="true" className="size-4" />
        New client
      </Button>
      <IconButton label="Delete the client">
        <Trash2 aria-hidden="true" className="size-4" />
      </IconButton>
    </div>
  ),
};

export const Large: Story = { args: { variant: "primary", size: "lg", children: "Start free" } };
export const Pending: Story = { args: { variant: "primary", pending: true, children: "Saving" } };
export const Disabled: Story = { args: { variant: "secondary", disabled: true } };

export const AsLink: Story = {
  render: () => (
    <ButtonLink href="/clients" variant="secondary">
      Open the client list
    </ButtonLink>
  ),
};
