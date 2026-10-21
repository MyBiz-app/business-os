import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { Copy, MoreHorizontal, Pencil, Trash2 } from "lucide-react";

import { Button, IconButton } from "./button";
import { Menu } from "./menu";
import { Popover } from "./popover";

const meta: Meta = { title: "Components/Menu and Popover", component: Menu };
export default meta;
type Story = StoryObj;

const icon = "size-4 text-muted";

export const ActionsMenu: Story = {
  render: () => (
    <div className="flex justify-end p-4">
      <Menu
        label="Client actions"
        trigger={(props) => (
          <IconButton label="More actions" variant="secondary" {...props}>
            <MoreHorizontal aria-hidden="true" className="size-4" />
          </IconButton>
        )}
        items={[
          { key: "edit", label: "Edit", icon: <Pencil aria-hidden="true" className={icon} />, href: "/clients/1/edit" },
          { key: "copy", label: "Copy the join link", icon: <Copy aria-hidden="true" className={icon} />, onSelect: () => undefined },
          { key: "sep", separator: true },
          { key: "delete", label: "Delete", icon: <Trash2 aria-hidden="true" className="size-4" />, tone: "danger", onSelect: () => undefined },
        ]}
      />
    </div>
  ),
};

export const NearTheBottomFlipsUp: Story = {
  render: () => (
    <div className="flex h-[calc(100vh-3rem)] items-end justify-start">
      <Menu
        label="Sort"
        placement="bottom-start"
        trigger={(props) => (
          <Button {...props} variant="secondary">
            Sort by
          </Button>
        )}
        items={[
          { key: "name", label: "Name", onSelect: () => undefined },
          { key: "recent", label: "Most recent", onSelect: () => undefined },
          { key: "value", label: "Highest value", onSelect: () => undefined },
        ]}
      />
    </div>
  ),
};

export const PopoverWithContent: StoryObj = {
  render: () => (
    <Popover
      label="Filter by status"
      className="w-72 p-4"
      trigger={(props) => (
        <Button {...props} variant="secondary">
          Filter
        </Button>
      )}
    >
      {({ close }) => (
        <div className="flex flex-col gap-3 text-sm">
          <p>Any content: a form, a list of options.</p>
          <Button variant="primary" onClick={close}>
            Apply
          </Button>
        </div>
      )}
    </Popover>
  ),
};
