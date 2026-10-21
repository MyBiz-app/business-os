# Legal pack for a lawyer's review (Amendment 13)

Drafts for **Israel's Privacy Protection Law, Amendment 13 (in force from August 2025)** and the
Privacy Protection Regulations (Data Security) 2017. They describe what the product does today so a
lawyer can check the wording in one sitting. **Nothing here is legal advice**; every statement of
law is marked "to confirm" and every placeholder is in `{braces}`. The company details are
fictitious until the owner registers the real company (go-live task).

| File | What it is | Language |
|---|---|---|
| [security-procedure.he.md](security-procedure.he.md) | The data security procedure (נוהל אבטחת מידע): roles, access, logging, encryption, backups, incidents, review | Hebrew |
| [data-inventory.md](data-inventory.md) | The data inventory (records of processing): what is held, why, on what basis, how long, by whom | English |
| [security-officer.md](security-officer.md) | The data security / privacy officer role: whether needed, duties, appointment text | English |
| [vendor-review.md](vendor-review.md) | Annual review of the sub-processors, with the checklist and the current list | English |

Related, already in the repository: the privacy policy, terms and data processing agreement shown on
the site (`apps/web` legal pages, drafts marked for a lawyer), [privacy review](../reviews/archive/privacy-2026-10.md),
[security review](../reviews/archive/security-2026-10.md), [on-call and incident response](../deploy/on-call.md),
[incident templates](../deploy/incident-templates.md).

## How MyBiz sits in the law (our understanding, to confirm)

- Each **business** that uses MyBiz is the controller (בעל מאגר) of its clients' data. MyBiz is the
  processor (מעבד מידע) for that data, under the data processing agreement.
- For **business owners and staff** (accounts, sign-in, billing, support), MyBiz is the controller.
- The data security regulations place duties on controllers, and on processors by contract. The
  tier of obligations (basic, medium, high) depends on the sensitivity and the number of people.
  The inventory lists health declarations, national ID numbers and bank details, which may raise
  the tier. **To confirm the tier with counsel.**

## What the lawyer is asked to decide

1. Is MyBiz required to appoint a privacy protection officer or a data security officer now, or
   only above a threshold (see [security-officer.md](security-officer.md))?
2. Which tier of the data security regulations applies to MyBiz as a processor, and to a typical
   business customer?
3. Are the retention periods right (leads and AI chats 12 months, message log and audit log 24
   months, a departed business 90 days, invoices and payroll records kept as the tax law requires)?
4. Is database registration with the Privacy Protection Authority needed for any of the databases
   in the inventory?
5. The wording of the breach notification steps (to the Authority, to businesses, to individuals)
   and the time limits in the procedure.
6. Approve the sub-processor list and the country of each, and whether a transfer outside Israel
   needs an extra step.
7. Replace every `{placeholder}` and the fictitious company details.

## Owner tasks that come out of this

- Appoint the officer and fill the name, phone and email in the procedure (section 2) and in the
  accessibility and privacy pages.
- Register the real company and replace the details in `packages/i18n/brand.json`.
- Book the lawyer's review (one session), and the annual vendor review (see
  [vendor-review.md](vendor-review.md)).
