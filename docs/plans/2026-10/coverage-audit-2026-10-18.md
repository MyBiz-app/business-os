# בדיקת כיסוי אפיונים: סבב 6, מוכנות לעלייה לאוויר (GL), סבב 7

תאריך: 18.10.2026. נבדק מול `main` ב-`e27cf5b` (היסטוריה מלאה, 575 קומיטים), קריאה בלבד. הבדיקה היא על הקוד, הבדיקות, המסמכים והמיגרציות, לא רק על כותרות ה-PR.

**מקרא:** ✅ בוצע · 🟡 בוצע חלקית (מפורט מה חסר) · 🔴 לא בוצע · ⏳ בעבודה / לא התחיל / בהמתנה (לא נבדק). פריט בתשלום שכבוי ויש לו מתג כיבוי וצעד ברשימת העלייה נחשב ✅.

## סיכום

| אפיון | ✅ | 🟡 | 🔴 | ⏳ |
|---|---|---|---|---|
| סבב 6 (27 פריטים) | 15 | 12 | 0 | 0 |
| מוכנות לעלייה (GL1-GL25) | 11 | 13 | 0 | 1 (GL25) |
| סבב 7 חלק א (R1-R20) | 8 | 6 | 0 | 6 |
| סבב 7 חלקים ב+ג (R21-R37b) | 6 | 6 | 0 | 7 |

הערות: (1) מספרי המיגרציות ב-main שונים מהתוכנית (ירדו או עלו באחד-שניים) אבל הרצף 0001-0135 תקין, בראש אחד ובלי חורים. (2) המיגרציה 0128 היא של GL (תפקיד למשימות רקע), לא של סבב 7. (3) הפריטים שנספרו 🟡 הם בעיקר "חסר פרט אחד או שניים", לא תכונה שלמה שנעלמה.

---

## 1. סבב 6

האפיון אינו כולל טקסט נפרד ל-T3 ול-P6 (נבדקו לפי PR, STATUS ו-DECISIONS). נספח א' נטמע בסעיף 10.

| פריט | סטטוס | עדות | פער |
|---|---|---|---|
| L1 סימולציית עלות | ✅ | #351 | - |
| K1 תעודות זהות | ✅ | #353, מיגרציה 0102, `tests/test_identities.py` | - |
| K2 סוג עסק ומוכנות משפטית | 🟡 | #354, מיגרציה 0103 | שער השכר מוצג בכרטיס אבל אף נקודת קצה של שכר לא אוכפת אותו; אין רמז "בדרך כלל נדרש רישיון" בחבילות התחום; לרישיון אין קובץ מצורף (מספר ותוקף בלבד) |
| T1 מנוע PDF בשרת | ✅ | #355 | - |
| F1 אזור הקבצים | ✅ | #361, 0104 | - |
| T2 תבניות מסמכים וסדרות | 🟡 | #367, 0105 | מסמכים שהונפקו לא נשמרים בתיקיית "מסמכי העסק" באזור הקבצים (אפיון 4.1) |
| T3 מסכי מסמכים ב-CRM | ✅ | #374 | - |
| P1 תיק עובד וטופס 101 | 🟡 | #364, 0106 | "הודעה לעובד" היא רק שדה תאריך, בלי מסמך שנוצר ובלי חתימה; PDF של 101 נוצר לפי דרישה ולא נשמר בתיקיית העובדים |
| P2 שעון נוכחות | ✅ | #362, 0107 | נדחו ובתיעוד: שעון מוגבל מיקום, ימי עבודה לעובד |
| P3 רכיבי שכר ובונוסים | ✅ | #371, 0108 | הערכת עלות מעסיק בטופס הבונוס נדחתה ולא נוספה |
| P4 ריצת שכר עד ברוטו | 🟡 | #372, 0109 | אין מודול `payroll` בתשלום ב-`commerce/modules.py` (שכר מוגבל רק בהרשאות); אין תזכורות ב-1 וב-5 בחודש; אין push "תלוש מוכן" לעובד; אין עלות מעסיק בכותרת הלוח |
| P5 נטו, תלוש PDF, מס"ב | 🟡 | #375 | חסרות יתרות חופשה/מחלה בתלוש (מתועד); תלושים לא נשמרים באזור הקבצים (T88); מדרגות מס וביטוח לאומי הן דוגמאות 2025 עד שרואה חשבון ימלא (מתועד) |
| P6 תלוש מתקן וסיכום שנתי | ✅ | #376, #379, 0112 | יתרות חופשה וזיכוי פנסיה נדחו (מתועד) |
| M1 ליבת ההגירה | 🟡 | #369, 0110 | אין פיצול "עסק חדש / עסק קיים" ב-`/start` ובעמוד הבית; המרכז נגיש רק בתוך ה-CRM; סוגי ייבוא חסרים (תלויים, תגיות, לידים/הערות/מסמכים, היסטוריית תשלומים, לוז שבועי קבוע) |
| M2 מיפוי חכם | 🟡 | #370 | אין קלט PDF/תמונה; תבניות רק ל-Google ו-Outlook, לא למערכות ישראליות; אין ייבוא אנשי קשר מהטלפון; מדריכי ייצוא בלי צילומי מסך |
| M3 הודעה ללקוחות וליווי | 🟡 | #373 | מסלול "עסק חדש" (תבניות תחום, מתג דמו, צ'קליסט 7 שלבים) לא נבנה; אין תור "הגירות" ייעודי בקונסולה (החלטה מתועדת) |
| D1 דמו ושחרור | ✅ | #377 | - |
| U1 הגדלת מפה ובורר סניפים | ✅ | #349 | אין בדיקת Playwright ייעודית (זניח) |
| U2 פורטרטים ושמות | 🟡 | #357, #368 | הפורטרט של סופי זמני (חיתוך מראה של ליה); שמות שונים מהאפיון (שירי, ליאו) בלי רשומת החלטה; אין עמוד אישור תצוגה מקדימה |
| U3 עריכת מבנה | 🟡 | #365, 0111 | תדריך בוקר לפי צוות עדיין לא (מתועד) |
| U4 משתני הודעה | 🟡 | #363 | `{branch_phone}` ו-`{balance_due}` לא מוצעים |
| U5 סרגל מסננים לתוכן | 🟡 | #350 | מספרי עוקבים בחלון הרשתות לא מוצגים |
| U6 ביקורת עיצוב | ✅ | #378 | הדוח והצילומים מחוץ לריפו |
| U7a טוקנים ולינט | ✅ | #383 | כלל "מרווח מחוץ לסקאלה" לא נוסף (אפס מקרים בבדיקה) |
| U7b שיווק וקונסולה | ✅ | #382 | - |
| U7c CRM | ✅ | #381 | - |
| U7d אפליקציה | ✅ | #380 | - |

---

## 2. מוכנות לעלייה לאוויר (GL1-GL25)

| פריט | סטטוס | עדות | פער |
|---|---|---|---|
| GL1 אימות דו-שלבי, סיסמאות, sessions | 🟡 | #386, 0113 | אין בדיקת e2e (Playwright) להרשמה ל-MFA. (תקרת חוסר פעילות בשרת וקודי גיבוי: סטיות מתועדות, תכונה בתשלום/לא נתמכת, לא נספרו כפער) |
| GL2 הפרדת סניפים בתתי-משאבים | 🟡 | #387 | חסרה בדיקה גנרית שנכשלת כשנתיב עם `{client_id}` לא עובר דרך עזר הסניף (סעיף 3 באפיון) |
| GL3 שמירות Production, קבצים, AI | ✅ | #388 | - |
| GL4 סריקות CI | ✅ | #384 | - |
| GL5 CSP, HSTS, noindex | 🟡 | #385 | אפליקציות ה-Expo ל-web (`apps/client-app/vercel.json`) בלי `X-Robots-Tag: noindex` ובלי robots, כלומר staging שלהן ניתן לאינדוקס |
| GL6 החלפת מפתח הצפנה | ✅ | #389 | - |
| GL7 יומן פעולות | 🟡 | #392, 0115 | שינויי מסלול/מודולים וייצוא CSV/דוח/PDF (חוץ משכר ויומן) לא נרשמים ב-`audit_log` |
| GL8 זכויות מידע | ✅ | #390, 0114 | - |
| GL9 הסכמה ו"הסר" | ✅ | #391, 0116 | - |
| GL10 גרסאות משפטיות | 🟡 | #394, 0117 | רכז הנגישות בלי טלפון ב-`brand.json` ובהצהרה (נתון שהבעלים צריך לספק) |
| GL11 נגישות | 🟡 | #395 | המעבר הידני עם NVDA/VoiceOver/TalkBack לא בוצע (הטבלה ריקה, דורש אדם עם מכשירים); בהצהרה אין תאריך בדיקה וטלפון רכז |
| GL12 Production כקוד | ✅ | #396 | - |
| GL13 ניטור והתראות | 🟡 | #400, 0119 | אין העלאת source maps ל-Sentry (אתר ואפליקציה); דף הבריאות מציג גודל מסד אבל לא גודל קבצים |
| GL14 משימות רקע בקנה מידה | ✅ | #398, 0120 | - |
| GL15 גיבוי שני ותרגול שחזור | 🟡 | #397 | שורת התרגול היחידה סינתטית; שחזור אמיתי ממתין לחשבון R2 (A2, תלוי בבעלים). מתג כיבוי וצעד ברשימה קיימים |
| GL16 שחרור ו-Rollback | 🟡 | #399 | rollback לא תורגל אף פעם על staging ("לא תורגל עדיין" בטבלת `releases.md`) |
| GL17 רשימות גדולות וחיפוש | 🟡 | #403, 0118 | ברשימות באפליקציה (Expo) אין cursor או "טען עוד"; רשימת הצעות ב-CRM חסומה ב-200 בלי המשך |
| GL18 עומס, מגבלת קצב, מכסה לעסק | 🟡 | #405 | אין כלל קצב ייעודי להעלאות קבצים; אין חישוב חיבורי מסד מול Supabase Pro; מספר הקיבולת ל-Starter ("כ-15 עסקים") הוא הערכה |
| GL19 מוכנות לחנויות | 🟡 | #404 | `eas build --profile production` לא הורץ; מזהה האפליקציה זמני (בהחלטה); אין source maps |
| GL20 חיוב: מע"מ, גבייה, ביטול | ✅ | #408, 0123 | החזר יחסי לא נבנה (החלטה T89, סליקה כבויה) |
| GL21 מכסות ומדדי מוצר | ✅ | #406, 0122 | - |
| GL22 מיילים שמגיעים | ✅ | #409, 0124 | 10/10 ב-mail-tester הוא צעד שלך אחרי A6 |
| GL23 תקלות ותיקון 13 | ✅ | #407, 0121 | שמות/כתובות בטיוטות הם צעדים שלך |
| GL24 חזרה גנרלית | 🟡 | #420 | הריצה הייתה ב-CI, לא ריצה מלאה על staging (rollback אמיתי, שחזור מ-R2, התראה לטלפון); שתי טענות ישנות/לא מגובות בטבלת הציונים (יציאה מכל המכשירים באפליקציה, "pool מחושב ב-production.md") |
| GL25 סדר קוד | ⏳ | #430 פתוח; כבר ב-main: #410, #414, #415, #416, #417 | `jobs.py` (950 שורות) ושאר `start-wizard.tsx` (654) עדיין לא |

### משימות שרק אתה עושה (A1-A12): מתג כיבוי וצעד ברשימה
✅ A1-A7, A9, A10, A11. 🟡 A8 (חברה/עוסק, חשבון בנק, ביטוח סייבר ואחריות מקצועית): אין צעד ב-`go-live-checklist.md` או `go-live-day.md`, רק בטבלת הציונים. 🟡 A12 (בדיקת חדירות מקצועית): אין צעד או טריגר ברשימה, רק אזכור בציונים. פערים קטנים: חלופת Cloudflare Pages ל-Vercel לא מתוארת; חשבונות Google ו-Apple לא מוזכרים ברשימת חשבונות עם MFA.

### נושאים מסעיפים 1-2 ללא שרשור או שלא נמצאו ב-main
כלל קצב להעלאות; WAF/Cloudflare (אין צעד ב-`production.md`, ברשימה או ב-runbook); חישוב pool מול Supabase Pro; גודל קבצים בדף הבריאות; source maps; תוסף ESLint לאבטחה (ruff `S` בלבד, ביטחון נמוך). סעיף 3 באפיון ("טוב מספיק") לא נסרק.

---

## 3. סבב 7 חלק א (R1-R20)

| פריט | סטטוס | עדות | פער |
|---|---|---|---|
| R1 ערכת רכיבים | 🟡 | #419 | פס התקדמות עליון למעבר מסלול איטי מ-300ms לא נבנה (`ProgressBar` מוגדר ולא בשימוש); אין בדיקות רכיב |
| R2 הודעות | 🟡 | #418 | אין שום שימוש באפשרות `action` (אין "בטל" אחרי מחיקה, אין "צפה" אחרי יצירה); בטוסט של האפליקציה הודעה אחת בלבד בתחתית, בלי ערימה |
| R3 בלי קפיצה לראש הדף ושלדים | 🟡 | #422 | אין `loading.tsx` לדשבורד ולדוחות (R3 השאיר ל-R4, ו-R4 לא הוסיף); תיקיות הקבצים אינן סלייסר מחליק |
| R4 דשבורד מחובר וטווח חופשי | ✅ | #423 | - |
| R5 כרטיס עובד | 🟡 | #426 | לשונית המסמכים בלי תלושים וחוזה; הכרטיס לא נפתח כחלון מרשימת הצוות ו"הזמן עובד" לא חלון; לשונית AI לא מפרטת לאילו סוכנים העובד פתוח (ביטחון בינוני) |
| R6a בועת AI | ✅ | #428 | - |
| R6b דף צוות AI | 🟡 | #427 | אשף הסוכן ועורך הסוכן עדיין עם `<dialog>` משלהם ולא עם Modal החדש |
| R7 מדריך ראשון | ✅ | #445, 0131 | - |
| R8 ניצול AI וכלכלה | 🟡 | #443, 0130 | אין ממשק לקניית משתמשי AI נוספים (רק `PUT /ai/extra-users`), והודעת `ai_users_full` מפנה לשם: מבוי סתום; חסרה בדיקת מחירון מול חשבונית Anthropic בקונסולה (ביטחון בינוני) |
| R9 קטלוג מאוחד | ✅ | #433 | אריח השירותים מציג מספר מפגשים ולא "נמכרו ב-30 יום" (קטן) |
| R10 חלונות ליד/לקוח/ייבוא/שיעור/תור | ✅ | #432 | - |
| R11 הצעות, אירועים, חלונות כספים | ✅ | #435 | אריח "אושרו החודש" סופר את כל ההצעות שאושרו |
| R12 תפריט צד | ⏳ | #438 פתוח | - |
| R13 הגדרות | ✅ | #424 | דרישת MFA לצוות לא תחת נושא אבטחה, והסכמות (GL9) לא תחת "נתונים ופרטיות" (ביטחון נמוך) |
| R14 פרופיל | ✅ | #429 | - |
| R15 רוחב מסכים | ⏳ | לא התחיל | - |
| R16 מעבר עיצוב | ⏳ | לא התחיל | - |
| R18 מילוי דמו | ⏳ | #457 פתוח | - |
| R19 סימולציית AI חיה | ⏳ | בהמתנה מכוונת | - |
| R20 סיום | ⏳ | לא התחיל | - |

חוצה-פריטים: מפתחות i18n זהים ב-he וב-en (6962 לכל קובץ), בלי חסר שנמצא בסריקה סטטית. נותרו 40 מופעי `<details>` גולמי ב-35 קבצים ו-`CollapsibleSection` בשימוש רק בפרופיל ובשלושה נושאי הגדרות (כרטיס לקוח, כרטיס עובד, דוחות, לוח שכר ועוד לא הומרו; סעיף 12.4). "נוח" הוחלף ל"ליאו" בכל מקום.

---

## 4. סבב 7 חלקים ב+ג (R21-R37b)

| פריט | סטטוס | עדות | פער |
|---|---|---|---|
| R21 מותג מודולרי | ✅ | #421, 0125 | - |
| R22 כתובת אתר לעסק ולסניף | ✅ | #434, 0127 | מקור ההרשמה הוא R25a |
| R23 הקפאה בבקשה ומנוי מתחדש | 🟡 | #449, 0135 | חסרים: קובץ מצורף לבקשה, הצעת AI להקפאה (שניהם "בהמשך" ב-STATUS); ברירות המחדל שונות מהחלטה 18.11 (מכסה שנתית ללא במקום 30 יום; ימים מקסימליים לבקשה 30 במקום 90, ביטחון בינוני) |
| R24 ליבת MyBiz Sites | ✅ | #447, 0132 | באשף ממולא מראש רק צבע המותג; כתובת השולח ב-`brand.json` עדיין `no-reply@example.com` (ברשימת העלייה) |
| R25a מסלולי הרשמה | ⏳ | #458 פתוח | - |
| R25b "האתר שלי" ב-CRM | ⏳ | #454 פתוח | - |
| R26 עמוד `/websites` | 🟡 | #440 | מחירים כפולים ב-`apps/web/src/lib/website-prices.ts` ושונים מ-`pricing.py` ב-USD/EUR (ILS תואם), בניגוד ל"הגדרה אחת"; אין רשומת STATUS (en/he); `/websites` חסר ברשימות המסלולים של e2e (`marketing.py`, `csp.py`, `screen_sweep.py`); בעמוד המחירים רק קישור טקסט, בלי תוספת אתר/"רק אתר" |
| R27 צוות AI בנחיתה | ✅ | #442 | - |
| R28 מצב עצמאי | ⏳ | לא התחיל | - |
| R29 מעברי עמודים | 🟡 | #441 | מעבר כרטיס-לחלון מחובר רק ללידים (לא תוכניות, שירותים, לקוחות, הצעות, חשבוניות, קבלות, תורים); אין `experimental.viewTransition` ב-`next.config.ts` (ייתכן שהמעבר לא פועל; ביטחון נמוך); אין מורף כותרת משותף ואין בדיקה |
| R30 רשימת המתנה חכמה | 🟡 | #450, 0134 | חסרים: מונה "N ממתינים" בשיעורים ובשעות; סליידר דו-ידית (יש כפתורי +/-); חלון ביטול חינם 30 דקות אחרי קידום מהמתנה; סינון מדריך/מיקום בבקשת לקוח |
| R31 רישום מעל מכסה | ✅ | #425, 0126 | אין שורת DECISIONS להחלטה 18.20 (זניח) |
| R32 מדיניות ביטולים לעסק | ⏳ | בבנייה | - |
| R33 ביטול מנוי MyBiz | ⏳ | #456 פתוח | - |
| R34 ערים ורחובות | 🟡 | #444, 0129 | אשף ההרשמה לא אוסף כתובת סניף (STATUS מציין); לא נמצאה כתובת הפרופיל האישי בייצוא נתונים (ביטחון נמוך) |
| R35 מפת סניפים | ⏳ | #446 פתוח | - |
| R36 עובד גם לקוח | 🟡 | #436 | כפתור "הוסף אותי" קיים ברשימת הלקוחות אבל לא ברשימת המשתתפים בשיעור (ובזרימת בעל מסעדה שמזמין שולחן); סינון "בלי עובדים" אומת רק במספרי הדשבורד (ביטחון בינוני) |
| R37a MCP קריאה | ✅ | #448, 0133 | - |
| R37b MCP פעולות | ⏳ | #451 פתוח | - |

מיגרציות סבב 7 בפועל ב-main: 0125 R21, 0126 R31, 0127 R22, 0129 R34, 0130 R8, 0131 R7, 0132 R24, 0133 R37a, 0134 R30, 0135 R23. הודעות הקומיט של R24 (0129) ושל R37a (0130) מצטטות מספרים ישנים; הקבצים וה-DECISIONS נכונים.

---

## English: real gaps (for the coordinator: new slices or fold into R20)

Priority A (functional holes, high confidence):
1. R8 dead end: `ai_users_full` tells users to add an AI user, but there is no UI to buy extra AI users (only `PUT /ai/extra-users`). Add the purchase/add control in settings or the staff card.
2. R26 pricing drift: `apps/web/src/lib/website-prices.ts` duplicates and disagrees with `apps/api/app/websites/pricing.py` for USD/EUR. Serve prices from one source; also add `/websites` to `e2e/marketing.py`, `e2e/csp.py`, `e2e/screen_sweep.py`, STATUS en/he entries, and the website add-on / "site only" choice on the pricing page.
3. R30 missing pieces: "N waiting" counter on classes/hours, two-handle range slider, 30-minute free-cancel grace after waitlist promotion, instructor/location filter on a request.
4. R23 missing pieces: request attachment, AI-suggested freeze, and align seeded defaults with decision 18.11 (yearly bank 30 days, max 90 days per request) or record the deviation.
5. R29: card-to-window transition only on leads; wire plans, services, clients, quotes, invoices, receipts, appointments. Verify `experimental.viewTransition` is needed/enabled in `next.config.ts`; add a test.
6. R36: "Add me" inside the class participant list; verify the "without staff" filter on all reports, not only dashboard numbers.
7. R34: collect the branch address in the sign-up wizard; confirm profile address is in data export (GL8 registry).
8. P4 (round 6): no paid `payroll` module in `commerce/modules.py` (payroll is permission-gated only), no 1st/5th reminders, no "payslip ready" push, no employer-cost headline on the run board; K2 payroll readiness gate is display-only (enforce server-side in run create/approve).
9. T2/P1/P5 (round 6): issued documents, Form 101 PDFs and payslips are never filed in the Files area (only payroll Excel and Masav are). Either file them or record a decision for T2 and P1 like T88.
10. M1/M3 (round 6): no new-vs-existing business split at `/start` and on the home page; "new business" track (templates, demo-data toggle, 7-step checklist) not built.
11. GL2: add the generic guard test that fails when a `{client_id}` route skips the branch helper.
12. GL5: `X-Robots-Tag: noindex` and robots for non-production Expo web deployments.
13. GL7: audit-log entries for plan/module changes and for CSV/report/PDF exports other than payroll and audit.

Priority B (polish / completeness, fold into R20 or R16):
14. R1: global top progress bar (`ProgressBar` unused); R2: use the toast `action` for Undo/View, app toast stack; R3: `loading.tsx` for dashboard and reports; sliding slicer on Files folders.
15. R12.4: replace ~40 raw `<details>` and the raw `<dialog>` in agent wizard/editor, agent dialog, shift board, payroll run board, over-capacity button, image crop with `CollapsibleSection`/`Modal`.
16. R5: staff card documents tab (payslips, contract), open as window from the team list, invite employee as window, AI tab listing agents open to the person.
17. GL17: cursor / "load more" in the Expo app lists; GL13: Sentry source maps (web and app) and file size on the health page; GL18: upload rate-limit rule and a connection-pool calculation against Supabase Pro.
18. Go-live docs: add steps for WAF (Cloudflare proxy or Vercel Firewall), bank account and insurance (A8), and the later penetration test (A12); fix the stale scorecard claims (sign-out-everywhere in the app, "pool sized in production.md"); add accessibility coordinator phone and test date once known.
19. Round 6 small items: M2 (PDF/photo input, Israeli-system templates, phone contacts, screenshots in guides), M1 extra import kinds, U2 (Sophie's final portrait, record the Shiri/Leo name decision), U3 briefing by team, U4 `{branch_phone}`/`{balance_due}`, U5 follower counts, P2 location-limited clock-in (R34 coordinates now exist).
20. R24: pre-fill more wizard fields than the brand colour; replace the `no-reply@example.com` sender placeholder (already a go-live step).

Owner-dependent, not code: GL11 manual NVDA/VoiceOver/TalkBack pass, GL15 real restore drill (needs R2 account), GL16 rollback practice on staging, GL19 first `eas build --profile production` and final app id, GL24 full staging rehearsal.
