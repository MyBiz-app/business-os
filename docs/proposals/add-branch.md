# Adding a branch (X28)

**Goal.** A network owner can add a branch at any time, through one form that captures what a
branch needs at the start and states clearly when it costs extra.

**Who.** Owners (permission `business.settings`). Managers without it do not see the page.

**Form (`/locations/new`).**
1. Price notice first, only when chargeable: price per extra branch, the extra-branch total before and
   after, "nothing is charged now". The submit needs the owner to tick that they accept it.
2. Name, address.
3. Opening hours: copy another active branch's week, or set them later on the branch page (default: copy the first).
4. Team: members kept to specific branches can be added to the new one (members with no branch limit already work everywhere).

**API.**
- `GET /locations/new-branch` returns currency, active branches, price per extra branch, monthly extras now / after.
- `POST /locations/new-branch` creates the branch with hours and team in one transaction; `409 charge_not_accepted` without the acceptance.
- `POST /locations` stays the low-level create.

**Billing.** Price comes from the `extra_location` module (first branch included). The module's quantity already follows the
active branches (T77), so the next invoice is right. No provider is charged (paid-provider rule).

**Not in this slice.** Per-branch service lists (services are business-wide), rooms at creation (added on the branch page), moving
clients between branches.
