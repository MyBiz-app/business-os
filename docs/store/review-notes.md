# Notes for the store reviewers

Paste into Apple's "App Review Information" (Notes) and Play's "App access" form. Reviewers cannot
receive a one-time code by email, so a test account with a fixed sign-in is created on the
production (or the staging) database right before submission. Never put the real password in this
repository; keep it in the stores' forms only.

## Test accounts to create at submission time

| Account | Role | Needs |
|---|---|---|
| `review-client@<final domain>` | A client of a demo business | The join code of a demo business |
| `review-owner@<final domain>` | Owner of a demo business with sample data | Two-step sign-in switched off for this account, or the reviewer given the code (note it in the form) |

## Text to paste (English)

MyBiz is a booking and business-management app. After signing in with an email and a one-time code,
a client sees their bookings, plans, receipts and messages from the businesses they joined; staff and
owners see the business area (schedule, clients, time clock, payslips).

Sign in with the demo account above (email and the password given in the form). To see a client's
view join the demo business with code `<code>`. Staff and owner screens appear automatically for the
owner account.

Permissions: notifications (reminders), camera and photos (profile picture only, asked when you tap
"take a photo" or "pick a photo"), Face ID (optional app lock). No location, no microphone, no
tracking, no ads. There are no in-app purchases: businesses subscribe on our website.

Delete account: Me → "Delete my account".

## טקסט להדבקה (עברית)

MyBiz היא אפליקציה לקביעת תורים ולניהול עסק. אחרי כניסה עם אימייל וקוד חד־פעמי, לקוח רואה את ההזמנות,
המנויים, הקבלות וההודעות מהעסקים שהצטרף אליהם; עובדים ובעלי עסק רואים את אזור העסק (יומן, לקוחות,
שעון נוכחות, תלושי שכר).

הרשאות: התראות (תזכורות), מצלמה וגלריה (תמונת פרופיל בלבד), Face ID (נעילת אפליקציה, לא חובה). אין מיקום,
אין מיקרופון, אין מעקב ואין פרסומות. אין רכישות בתוך האפליקציה: עסקים נרשמים באתר.

מחיקת חשבון: אני → "מחיקת החשבון שלי".

## Before every submission

1. Re-read [`data-safety.md`](data-safety.md) against what was added since the last release.
2. Confirm the privacy policy and terms pages are live on the final domain.
3. Check that the test accounts still sign in, and that the demo business still has sample data.
