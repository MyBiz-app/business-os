# בדיקת כיסוי חוזרת (18.10.2026, אחרי 21 מיזוגים נוספים)

נבדק מול `main` העדכני (מיגרציות 0001-0140, ראש אחד). קריאה בלבד: קוד, בדיקות ומסמכים נקראו, **לא הורצו** (אין Postgres ו-node_modules בסביבת הבדיקה; ב-GitHub לא נקראו לוגים של e2e). הקובץ הקודם: `coverage-audit-2026-10-18.md`.

בעבודה ולא נספרים כחסר: R33 (#456), R18 (#457), GL25 (#430). R19 בהמתנה מכוונת.

## 1. סיכום

| אפיון | ✅ | 🟡 | ⏳ בעבודה | 👤 רק אתה |
|---|---|---|---|---|
| סבב 6 (29 פריטים) | 20 | 9 | 0 | רשימה בסעיף 4 |
| מוכנות לעלייה (GL1-25) | 11 + 2 עם צעד אצלך | 8 + 3 תלויי בעלים | 1 (GL25) | A1-A12 כולם |
| סבב 7 R1-R20 | 8 | 9 (R1, R2, R3, R5, R8, R12, R15, R16, R20) | 1 (R18) | R19 וסנכרון מקומי |
| סבב 7 R21-R37b | 11 | 7 (R25a, R28, R29, R32, R35, R36, R37b) | 1 (R33) | רשימה בסעיף 4 |

אין אף פריט "לא בוצע". נסגרו מאז הבדיקה הראשונה, בין השאר: מודול שכר בתשלום ושער שכר בשרת, שמירת תלושים/101/חשבוניות באזור הקבצים, תזכורות ו-push לשכר, כרטיס עלות מעסיק, פיצול עסק חדש/קיים ב-`/start`, מסלול "עסק חדש", בדיקה גנרית לנתיבי לקוח (GL2), noindex ל-Expo web (GL5), רישום ביומן של מסלולים/מודולים (GL7), כלל קצב להעלאות ותקציב חיבורים (GL18), צעדי WAF/A8/A12 ברשימת העלייה, ממשק קניית משתמשי AI (R8), אשף ועורך הסוכן על Modal, אריח "אושרו החודש", מחירי האתרים במקור אחד (R26), "הוסף אותי" ברשימת משתתפים, כתובת סניף בהרשמה, והשלמות ההמתנה (R30) וההקפאה (R23).

## 2. מגבלות רשימת ההמתנה (R30): מכוסה

"המגבלה" באפיון (סעיף 28.2) היא **עד 5 בקשות פעילות ללקוח בעסק**. היא נאכפת (`MAX_ACTIVE_REQUESTS = 5` ב-`apps/api/app/schedule/waitlist.py`, תשובת 409 `too_many_requests`) ויש בדיקה: החמישית עוברת והשישית נכשלת. גם חלון הרישום האוטומטי 0-72 שעות נאכף במסד וב-API. פערים קטנים: אין בדיקות גבול ל-73 ול-(-1), והבדיקה של 5 הבקשות לא בטוחה מול שתי בקשות במקביל (חומרה נמוכה).

## 3. פערים אמיתיים שנותרו

### א. דורשים קוד (לפי עדיפות)

| # | פער | מקור | ביטחון |
|---|---|---|---|
| 1 | **ה-e2e אדום על main** בארבעת המיזוגים האחרונים שנבדקו, ושני issue של ריצה לילית פתוחים (#452 e2e, #455 pnpm-audit/trivy). R20 לא השיג "הרצת e2e מלאה" | R20 | גבוה |
| 2 | **פרטיות במפת הסניפים:** שכבת "מאיפה מגיעים לקוחות" מציגה גם עיר עם פחות מ-5 לקוחות. צריך `HAVING count(*) >= 5` בשאילתת `client_origins` ב-`branch_insights.py` ועדכון הבדיקה (שהיום בודקת עיר עם לקוח יחיד) | R35 | גבוה |
| 3 | R32: מדיניות הביטולים הכתובה (`GET /client/cancellation-policy`) לא מוצגת בשום מקום באפליקציית הלקוח, בדף ההצטרפות או בהרשמה; השגיאות `period_quota_reached` ו-`no_show_limit` לא ממופות להודעות ללקוח (מקבל שגיאה כללית) | R32 | גבוה / בינוני-גבוה |
| 4 | R36: מסנן "בלי עובדים" רק בדשבורד, לא בעמוד `/reports` ובדוחות הפירוט, סניף, שעות עמוסות וסיכון | R36 | גבוה |
| 5 | R29: מעבר כרטיס-לחלון לא מחובר ללקוחות, קבלות ותורים; אין `experimental.viewTransition` ב-`next.config.ts` (ההשפעה בפועל לא אומתה); אין בדיקה ואין רשומת DECISIONS | R29 | גבוה (חיווט) |
| 6 | R1/R2/R3: פס התקדמות עליון לא מורכב באף layout; ל-`action` בהודעה (בטל/צפה) אין אף שימוש, והודעת האפליקציה לא נערמת; אין `loading.tsx` לדשבורד ולדוחות; תיקיות הקבצים לא סלייסר מחליק | R1-R3 | גבוה |
| 7 | R16: לא נעשה מעבר מסך-מסך ולא נכתב דוח לפני/אחרי; נשארו 24 קבצים עם `<details>` גולמי (כרטיס לקוח, כרטיס עובד, דוחות) ללא קיפול (סעיפים 12.2/12.4). R15: אין צילומים ב-4 רוחבים, הקונסולה ועמודי החשבון לא טופלו, הבדיקה היחידה היא grep של מחרוזות | R15, R16 | גבוה |
| 8 | R5: בכרטיס עובד: לשונית מסמכים בלי תלושים וחוזה, לא נפתח כחלון מרשימת הצוות, אין רשימת "סוכנים הפתוחים לעובד", סעיפים לא מתקפלים | R5 | גבוה |
| 9 | R12: אין בדיקות, אין רשומה ב-`design-system.md`, אין צעד e2e | R12 | גבוה |
| 10 | R20 מסמכים: STATUS.md ו-STATUS.he.md עם "עודכן לאחרונה 16.10.2026", בלי שורות R2, R6b, R10, R15, R16; ב-DECISIONS אין R12/R15/R16 והמזהה X58 מופיע פעמיים; ב-STATUS מספרי מיגרציה שגויים ל-R30 (0136 במקום 0134), R7 (0132 במקום 0131) ו-R23, ערכים כפולים ל-R24/R37a/R23, אין רשומה ל-`/websites`, משפט M3 ישן בשורה 120, וב-DECISIONS:263 כתוב "נוח" במקום ליאו. אין issues או labels לסבב 7 ב-GitHub (#38/#35 ישנים) | R20 | גבוה |
| 11 | R37b: מדריך החיבור בלי צילומי מסך; אין פעולות "שלח הודעה" ו"החזר ביקור" | R37b | גבוה |
| 12 | R35: בחלונית הסניף חסרים הוצאות ומספר עובדים; אין בדיקת web או e2e למפה | R35 | גבוה |
| 13 | R28: אין בדיקות web ללוגיקת התפריט והדשבורד העצמאיים; בהגדרות עדיין מוצגים תפקידים במצב עצמאי | R28 | בינוני |
| 14 | GL13: דף הבריאות בלי גודל קבצים; חיבור source maps ל-Sentry לא נבדק (`@sentry/react-native` מוצהר רק ב-`app-kit`, ויבוא `@sentry/nextjs/config` לא אומת) | GL13 | בינוני |
| 15 | GL17: ברשימות האפליקציה offset וכפתור "עוד" רק בשתי רשימות, בלי cursor או טעינה בגלילה | GL17 | גבוה |
| 16 | GL7: ייצוא CSV של מכירות ותוכן ודפי דוחות לא נרשמים ביומן; אין בדיקה לרשומות `export.*` החדשות | GL7 | בינוני |
| 17 | GL1: אין בדיקת e2e להרשמה ל-MFA | GL1 | בינוני |
| 18 | GL10: שדה טלפון רכז נגישות חסר ב-`brand.json` (אפשר להוסיף את השדה וההצגה עכשיו, הערך שלך) | GL10 | גבוה |
| 19 | שכר: משימות ה-push לשכר מופיעות רק בקבצי workflow של staging; לוודא שיש מתזמן ל-production | סבב 6 | נמוך-בינוני |
| 20 | מסמכי עלייה ישנים: שורה 47 בטבלת הציונים עדיין מונה את פער "טען עוד" שנסגר ב-#431; שורת ה-WAF בציונים ו-`go-live-day.md` לא מצביעים על הסעיפים החדשים | GL24 | גבוה |
| 21 | R8: מגבלות משתמשי AI בחבילה לא מופיעות בעמודי המחירים; אין בקונסולה בדיקת מחירון מול חשבונית Anthropic | R8 | בינוני |

### ב. פערים קטנים ומתועדים (אפשר להשאיר)
P1 "הודעה לעובד" כשדה תאריך בלבד; P5 בלי יתרות חופשה/מחלה ועם מדרגות מס ובל"ל כדוגמאות עד אימות רואה חשבון; M1 רק 5 סוגי ייבוא; M2 בלי PDF/תמונה, בלי תבניות למערכות ישראליות ובלי צילומי מסך; K2 בלי רמז רישיון בחבילות תחום ובלי קובץ לרישיון; תדריך בוקר לפי צוות; `{branch_phone}` ו-`{balance_due}`; מספרי עוקבים; שעון נוכחות מוגבל מיקום; R25b בלי שורת סיכום חודשי במייל (אין מייל כזה); R34: כתובת בית של עובד לא בייצוא העסק (ביטחון נמוך); R30 בלי בדיקות גבול; כמה קישורים ואריחים קטנים בדשבורד והגדרות.

## 4. פריטים שרק אתה יכול לסגור

| נושא | מה צריך | מצב בקוד |
|---|---|---|
| חשבונות ותשלומים A1-A12 (Sentry, UptimeRobot, R2, Supabase Pro, Render Starter, Vercel Pro, דומיין ו-Resend, עורך דין, Apple/Google, MFA בחשבונות, ממונה אבטחה, בדיקת חדירות) | חשבונות, תשלום, החלטות | לכולם מתג כיבוי וצעד ב-`docs/deploy/go-live-checklist.md` (כולל A8, A12, WAF שנוספו ב-#459) |
| אימות דומיין שולח `mybizapp.click` (A6) | אתה | הקוד מוכן וכבוי עד אימות |
| עורך דין | טקסט ביטול מנוי MyBiz (R33) ו-`/legal/cancellation`; טיוטות GL23; הערת עורך דין על סיום מנוי בהגדרות R32 | טיוטות קיימות |
| החלטת חבילה "עצמאי" ב-129 ש"ח (איך מציגים הנחת חבילה בחשבונית) | החלטה | מסלול R25a/R28 העצמאי לא נבנה עד להחלטה |
| סקר מחירי מתחרים לאתרים (5-10 ספקים ישראליים + Wix) | אתה/מחקר | המחירים בקונפיגורציה, אין חיוב עד #46 |
| תשלום והחלטות | מחירי OpenAI/Gemini לאימות מול הספקים; מחיר מודול השכר האמיתי; ספק שכר חיצוני | ספקים כבויים, מחיר זמני |
| שכר | אימות רואה חשבון של מדרגות מס, ביטוח לאומי ופריסת התלוש (סימן "טיוטה" עד אז); פרטי חברה אמיתיים ב-`brand.json` | כבוי/סימן מים |
| מכשירים ידניים | מעבר NVDA/VoiceOver/TalkBack (GL11) ותאריך בדיקה לנגישות; בדיקת סליידר הטווח וקישורי Waze/Google Maps במכשיר אמיתי | רשימת בדיקה ריקה |
| שחזור ותרגול | שחזור גיבוי אמיתי אחרי חשבון R2 (GL15); תרגול rollback ב-staging (GL16); בניית production ראשונה ב-EAS ושם סופי לאפליקציה (GL19, מזהים בלתי הפיכים); חזרה גנרלית מלאה ב-staging (GL24); אימות תקרת חיבורי Supabase מול תקציב 60 | מסמכים מוכנים |
| MCP | הוספת המחבר ל-Claude ול-ChatGPT בחשבון אמיתי, צילומי מסך למדריך, רישום בספריות | הקוד מוכן |
| אתרים | בחירת אירוח לכל הזמנת אתר ואישור אירוח בתשלום | הקונסולה מציגה פרומפט ו-ZIP |
| R19 | סימולציית AI חיה (עולה כסף) | `python -m app.ai.live_sim` מסרב בלי אישורך |
| R20 | סנכרון `C:\dev\business-os` (דורש כרטיס אישור של מכשיר), פריסת Vercel אחת, בדיקת דומיין/DNS/SSL | אין מה לבנות |
| תמונת סופי | פורטרט סופי (Sophie) | תמונה זמנית |

---

## English: real gaps for fix slices

1. **E2E red on main** for the last 4 merges; nightly issues #452 (e2e) and #455 (pnpm-audit, trivy) open. Diagnose and fix first (blocks R20's "full e2e").
2. **R35 privacy:** `branch_insights.client_origins` needs a minimum of 5 clients per city (`HAVING count(*) >= 5`), update its test. Add expenses and employee count to the branch panel and a test for the map.
3. **R32 client side:** show `GET /client/cancellation-policy` in the client app, join page and first sign-up; map `period_quota_reached` and `no_show_limit` to client messages (`session-card.tsx`, `appointment.tsx`, i18n).
4. **R36:** "without staff" filter on `/reports` and the breakdown, branch, busy-hours, at-risk reports.
5. **R29:** wire card-to-window for clients, receipts, appointments/sessions; verify/enable `experimental.viewTransition`; add a test and a DECISIONS entry.
6. **R1/R2/R3:** mount the route progress bar; use toast `action` (Undo/View) at real call sites and stack toasts in the app; `loading.tsx` for dashboard and reports; sliding slicer on Files folders.
7. **R16/R15:** real screen-by-screen pass with before/after report; convert the 24 remaining raw `<details>` files (client card, staff card, reports) to `CollapsibleSection`; screenshots at 390/1440/1920/2560, cover console and account, replace the grep-only test.
8. **R5:** staff card documents tab (payslips, contract), open as window from team list and invite as window, list of agents open to the person, collapsible sections.
9. **R12:** tests, `design-system.md` entry, e2e step.
10. **R20 docs/GitHub:** refresh STATUS.md and STATUS.he.md (date, Now/Next, missing slice lines R2/R6b/R10/R15/R16, `/websites`, duplicates, wrong migration numbers for R30/R7/R23, stale M3 line at :120); DECISIONS (R12/R15/R16, duplicate X58, "Noah" -> Leo at :263); create round-7 issues and labels per CLAUDE.md; close stale #38/#35.
11. **R37b:** connector guide screenshots (owner partly), connector actions send-message and give-visit-back.
12. **R28:** web tests for solo menu/dashboard; hide roles in solo settings. **R25b:** monthly summary line (needs an email that does not exist; low).
13. **GL13:** file size on the health page; verify Sentry source-map wiring with a dummy-token build. **GL17:** keyset/"load more" in Expo lists. **GL7:** audit-log sales/content CSV and report prints, test `export.*`. **GL1:** MFA enrolment e2e. **GL10:** add accessibility coordinator phone field/render to `brand.json`.
14. **Payroll jobs:** confirm a production scheduler exists for the payroll push/reminder jobs (only staging workflows found).
15. **Stale go-live docs:** scorecard line 47 (quotes "load more" closed by #431), WAF row and `go-live-day.md` should link the new WAF/A8/A12 sections.
16. **R8:** AI-user limits on pricing pages; console check of the AI price table against the Anthropic invoice.
17. **R30 (small):** boundary tests for `waitlist_auto_hours` (-1, 73) and make the 5-request cap race-safe.
18. **Round 6 leftovers (low):** P1 notice-to-employee document, P5 leave balances, M1/M2 extras, K2 licence hint/file, U3/U4/U5 small items, location-limited clock-in.
