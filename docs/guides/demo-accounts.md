# Demo accounts (staging)

Which email is which role. Sign-in is by email code (OTP) in the app and the web; the plus
addresses all land in the one real inbox. Decision T91 in [`DECISIONS.md`](../DECISIONS.md).

| Email | What it is |
|---|---|
| `adire7399@gmail.com` | MyBiz primary owner: the console (always asks for a 2FA code). Also owner of the demo studio "סטודיו פלואו (דמו)" and a client of it: switch between the owner and the client view in the app. |
| `adired7399@gmail.com` | Owner of the full demo (Adir Fitness with 5 branches, Sharon Tennis Club, Blade Barbers, Merhav clinic) and also a client of each of them (`asclient`), so the app shows both sides. Exempt from 2FA on staging (`API_MFA_DEMO_EXEMPT_EMAILS`). |
| `adired7399+manager@gmail.com` | Network manager of Adir Fitness |
| `adired7399+branch@gmail.com` | Branch manager (Tel Aviv, strength) |
| `adired7399+coach@gmail.com` | Coach (Ramat Gan, yoga) |
| `adired7399+barber@gmail.com` | Barber (Florentin) |
| `adired7399+clinic@gmail.com` | Front desk (Petah Tikva clinic) |
| `adired7399+cust@gmail.com` | Test customer of the gym, tennis club, barbers and clinic |
| `adired7399+friend@gmail.com` | The test customer's friend |
| `*@example.invalid` | Fictitious demo people (clients, coaches, the six console customers). No mailbox. |

`adiredri73@gmail.com` is not a real mailbox and is retired; `--move-owner-from` hands its
businesses to the real one.

## Commands

Each plus address signs up once (email code), then the seed links it to its role. Run from
the **Seed staging demo data** workflow:

1. Hand over the old owner: owner_email = `adired7399@gmail.com`, move_owner_from = `adiredri73@gmail.com`.
2. Refresh the full demo: demo = `full`, owner_email = `adired7399@gmail.com` (links the plus logins).
3. Owner as client of every business they own: demo = `asclient`, owner_email = `adired7399@gmail.com`.
4. Studio + client for the primary owner: demo = `ownerclient`, owner_email = `adire7399@gmail.com`.
