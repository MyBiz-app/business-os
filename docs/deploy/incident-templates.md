# Incident message templates

Ready-to-send texts for the three kinds of notice. Each has a banner (shown in the web app and the
mobile app until resolved, opened in the MyBiz console under **Incident banners**), and a longer
email for businesses (send it from the console's **Broadcasts**, type "service", audience "Business
owners"). Fill the `{...}` parts, keep it short, say what we know and when the next update comes.

Rules:

- Say what is affected and what is not. Never guess a cause in public.
- Give the time of the next update, and keep it.
- No personal data in a notice. Never name a customer.
- A security event that touches personal data has legal clocks: read "Suspected data exposure" in
  [on-call](on-call.md) first, and have a lawyer read the customer email before it goes out.
- When it is over: resolve the banner, send one closing line, write the note in
  `docs/incidents/YYYY-MM-DD-title.md`.

## 1. Incident (something is broken)

Banner (type "Incident"):

| | Title | Details |
|---|---|---|
| Hebrew | יש לנו תקלה ב{החלק שנפגע} | אנחנו מטפלים בזה. עדכון הבא ב-{שעה}. |
| English | We have a problem with {the affected part} | We are working on it. Next update at {time}. |

Email to businesses:

> **Hebrew**
> נושא: תקלה ב-MyBiz: {החלק שנפגע}
>
> שלום,
> מ-{שעה} יש תקלה ב{החלק שנפגע}. מה לא עובד: {פירוט}. מה כן עובד: {פירוט}.
> אנחנו מטפלים בזה ונעדכן שוב ב-{שעה}. אין צורך לעשות דבר.
> {אם צריך: ההזמנות שנקבעו בזמן התקלה נשמרו / ייתכן שתצטרכו לבצע שוב ...}
> סליחה על אי הנוחות. לשאלות: {כתובת התמיכה}.
> צוות MyBiz
>
> **English**
> Subject: MyBiz problem: {affected part}
>
> Hello,
> Since {time}, {the affected part} has not been working properly. What is affected: {details}.
> What still works: {details}. We are working on it and will update you again at {time}.
> You do not need to do anything. {If needed: what to redo.}
> We are sorry for the trouble. Questions: {support address}.
> The MyBiz team

Closing line (email or banner text just before resolving):

> Hebrew: התקלה ב{החלק שנפגע} טופלה ב-{שעה}. סליחה על אי הנוחות.
> English: The problem with {the affected part} was fixed at {time}. We are sorry for the trouble.

## 2. Planned maintenance

Open the banner a day ahead (type "Planned maintenance"), and resolve it when done.

| | Title | Details |
|---|---|---|
| Hebrew | תחזוקה מתוכננת ב-{תאריך} | בין {שעה} ל-{שעה} המערכת תהיה זמינה חלקית. |
| English | Planned maintenance on {date} | Between {time} and {time} the system will be partly unavailable. |

Email, three days ahead for anything longer than 15 minutes:

> **Hebrew**
> נושא: תחזוקה מתוכננת ב-MyBiz ב-{תאריך}
>
> שלום, ב-{תאריך} בין {שעה} ל-{שעה} נבצע תחזוקה. בזמן הזה {מה לא יעבוד}. ההזמנות והנתונים
> נשמרים. אם יש לכם שיעורים באותה שעה, כדאי להכין את הלקוחות מראש. תודה על ההבנה.
>
> **English**
> Subject: Planned MyBiz maintenance on {date}
>
> Hello, on {date} between {time} and {time} we will do maintenance. During it {what will not
> work}. Bookings and data are safe. If you have classes at that time, you may want to tell your
> clients ahead. Thank you for understanding.

## 3. Security event

Use the banner only when people need to act or will notice (for example, forced sign-out). Type
"Security event".

| | Title | Details |
|---|---|---|
| Hebrew | עדכון אבטחה | לצורך הגנה על החשבונות ייתכן שתתבקשו להתחבר מחדש. אין צורך לשנות סיסמה אלא אם נודיע. |
| English | Security notice | To protect accounts you may be asked to sign in again. No need to change your password unless we tell you. |

Email to businesses when personal data may have been exposed (a lawyer reviews it first; fill the
facts only from the incident note, never from a guess):

> **Hebrew**
> נושא: הודעה חשובה על אבטחת המידע ב-MyBiz
>
> שלום,
> ב-{תאריך} זיהינו {תיאור קצר של האירוע}. מה ידוע לנו: {סוגי המידע שנפגעו, מספר משוער של
> אנשים, מה לא נפגע}. מה עשינו: {בלימה, החלפת מפתחות, תיקון}. מה אנחנו ממליצים לכם:
> {פעולה, אם יש}. הודענו לרשות להגנת הפרטיות {אם הודענו}. נעדכן שוב ב-{תאריך}.
> לשאלות: {כתובת התמיכה}. סליחה על כך.
> צוות MyBiz
>
> **English**
> Subject: Important notice about MyBiz data security
>
> Hello,
> On {date} we detected {short description}. What we know: {types of data involved, rough number
> of people, what was not affected}. What we did: {containment, key rotation, fix}. What we
> recommend: {action, if any}. We have notified the Privacy Protection Authority {if we have}.
> We will update you on {date}. Questions: {support address}. We are sorry.
> The MyBiz team

When a business must tell its own clients (it is the controller of their data), send it a short
text it can forward, with the same facts, and offer to help.

## Where the status page fits

The status page address (go-live checklist, owner task) goes in the banner's "Status page address"
field. Until there is one, leave it empty: the banner then shows only the text.
