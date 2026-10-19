# Roles, permissions and removing catalog items (October 2026)

Part of the CRM upgrade ([plan](crm-upgrade-2026-10.md)). Owner request, 2026-10-10.

## Principles

- **The API is the authority.** Every action is checked server-side against the member's effective
  permissions (system role bundle, or the exact switches of their custom role). The UI only hides
  what the API would refuse: a person without a permission does not see the button, link or menu
  item at all, not a disabled one.
- Nobody can hand out a permission they do not have (already enforced).

## What changes

1. **See roles before creating one.** The roles page lists the built-in roles (owner, manager,
   front desk, staff) with every permission marked allowed / not allowed, then the business's own
   roles, then the "new role" form.
2. **See and change a person's permissions.** Each team row has a "Permissions" popover with what
   that person can actually do (`permissions` on the team API). Changing it = picking another role
   for them (built-in or custom) in the same row; the popover links to the roles page.
3. **Removing catalog items.** New permission `catalog.delete`, in the owner and manager bundles
   only (a custom role can switch it on). `DELETE /services/{id}` and `DELETE /plans/{id}`
   (memberships and punch cards are plans):
   - nothing refers to the item: it is deleted;
   - sessions or sales refer to it: it is archived (`active = false`), so history, receipts and
     existing purchases stay valid. The response says which (`deleted` / `archived`).
   The delete button asks for confirmation and appears only with `catalog.delete`.
4. **Demo users.** One manager and one employee in a `networks` demo business, to check the above.

## Not in this slice

Per-person permission overrides on top of a role (a custom role per person covers it for now);
audit trail of catalog deletions.
