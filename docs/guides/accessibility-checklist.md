# Accessibility checklist (Israeli Standard 5568, WCAG 2.1 AA)

Go-live slice GL11. Two layers: an automated layer that runs on every merge to `main`, and a manual
pass by a person before launch and after big UI changes.

## Automated (runs in CI)

`e2e/dod.py` runs axe (serious and critical findings fail the run) on:

- the public pages, the sign-in screens and the business web app: every static screen (about 45) in
  Hebrew/light and English/dark, and the client app's schedule, home, bookings and profile;
- `e2e/agents.py` (AI team, content studio, console broadcasts and AI board) and `e2e/round6.py`
  (payroll, move to MyBiz, documents) run axe on their screens and fail on findings too.

To add a screen: add its path to `pages` in `e2e/dod.py`.

Result of the first full run (17 October 2026, after the round 6 redesign U7d): three findings across
the whole sweep, all fixed in the GL11 pull request:

| Screen | Finding | Fix |
|---|---|---|
| `/schedule` (both languages) | scrollable calendar region could not take keyboard focus | the grid is a focusable, named region |
| `/invoices/new` | low contrast on the "complete your details" link inside a warning note | link uses the text color with an underline |
| roles screen | permission labels for payroll proposals and AI team management were missing (raw keys shown) | translations added |

## Manual pass (a person, before launch)

Screen readers: NVDA with Firefox or Chrome on a PC; VoiceOver on an iPhone; TalkBack on Android.
Also: keyboard only (Tab, Shift+Tab, Enter, Space, Esc, arrows), 200% zoom, a 320 px wide window,
Windows high contrast, reduced motion on.

For each of the six main journeys, do it start to finish with the screen reader and the keyboard only,
in Hebrew and once in English. Tick when it works; note the problem and the screen otherwise.

| # | Journey | Where | NVDA | VoiceOver | TalkBack | Notes |
|---|---|---|---|---|---|---|
| 1 | Sign up, confirm the email, create a business | web | [ ] | [ ] | n/a | |
| 2 | Add a client and sell a membership | CRM | [ ] | n/a | n/a | |
| 3 | Create a session and book a client | CRM | [ ] | n/a | n/a | |
| 4 | Join a business with a code, book a class, cancel it | client app | [ ] | [ ] | [ ] | |
| 5 | Clock in and out, request time off | business app | [ ] | [ ] | [ ] | |
| 6 | Ask the AI assistant a question and read the answer | CRM | [ ] | n/a | n/a | |

Things to listen for: every control has a name and a role; headings and landmarks let you jump; errors
are announced and tied to their field; dialogs trap focus and return it; toasts are announced without
moving focus; the calendar grid is reachable and readable; nothing relies on color alone.

Manual pass status: **not done yet.** It needs a person with the devices. Record the date, the tester
and the results in the table above, then update the date in the accessibility statement.

## Statement

The public statement lives at `/legal/accessibility` (texts in `marketing.legal.accessibility` in the
translation files). It still needs, as a legal duty, the name, phone and email of the accessibility
coordinator; those come from the legal pages slice (GL10) and the owner.
