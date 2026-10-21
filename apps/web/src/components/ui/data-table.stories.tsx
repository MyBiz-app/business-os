import type { Meta, StoryObj } from "@storybook/nextjs-vite";

import { Badge } from "./badge";
import { DataTable, type DataTableColumn } from "./data-table";
import { useDataTable } from "./use-data-table";

type Client = { id: string; name: string; phone: string; plan: string; visits: number; status: "active" | "paused" };

const CLIENTS: Client[] = [
  { id: "1", name: "Dana Levi", phone: "+972 50 123 4567", plan: "Unlimited", visits: 42, status: "active" },
  { id: "2", name: "דנה כהן", phone: "+972 52 765 4321", plan: "10 classes", visits: 7, status: "active" },
  { id: "3", name: "Omar Haddad", phone: "+972 54 555 0101", plan: "Unlimited", visits: 19, status: "paused" },
];

const COLUMNS: DataTableColumn<Client>[] = [
  { key: "name", header: "Name", sortable: true, cell: (c) => <span dir="auto" className="font-medium">{c.name}</span> },
  { key: "phone", header: "Phone", nowrap: true, cell: (c) => <bdi dir="ltr">{c.phone}</bdi> },
  { key: "plan", header: "Plan", hideBelow: "md", sortable: true, cell: (c) => c.plan },
  { key: "visits", header: "Visits", align: "end", sortable: true, cell: (c) => c.visits },
  { key: "status", header: "Status", cell: (c) => <Badge tone={c.status === "active" ? "success" : "neutral"}>{c.status}</Badge> },
];

const meta: Meta = { title: "Components/DataTable", component: DataTable };
export default meta;
type Story = StoryObj;

export const Static: Story = {
  render: () => <DataTable columns={COLUMNS} rows={CLIENTS} rowKey={(c) => c.id} label="Clients" />,
};

export const Compact: Story = {
  render: () => <DataTable columns={COLUMNS} rows={CLIENTS} rowKey={(c) => c.id} label="Clients" density="compact" />,
};

export const Empty: Story = {
  render: () => <DataTable columns={COLUMNS} rows={[]} rowKey={(c) => c.id} label="Clients" empty={<p className="card p-6 text-center text-muted">No clients yet</p>} />,
};

function SortableAndSelectable() {
  const table = useDataTable({
    rows: CLIENTS,
    rowKey: (c) => c.id,
    sortValues: { name: (c) => c.name, plan: (c) => c.plan, visits: (c) => c.visits },
  });
  return (
    <DataTable
      columns={COLUMNS}
      rows={table.rows}
      rowKey={(c) => c.id}
      label="Clients"
      sort={table.sort}
      onSortChange={table.onSortChange}
      selection={{ selected: table.selected, onToggle: table.toggle, onToggleAll: table.toggleAll, allLabel: "Select all", rowLabel: (c) => `Select ${c.name}` }}
    />
  );
}

export const SortAndSelect: Story = { render: () => <SortableAndSelectable /> };
