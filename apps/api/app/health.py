"""Health declaration forms, per vertical (fitness: the questions Israeli gyms ask).

The form text is content, so it lives here by locale. Each signed declaration stores the
questions and statement exactly as shown, so changing the form never rewrites history."""

from dataclasses import dataclass


@dataclass(frozen=True)
class HealthForm:
    key: str  # stored with each declaration; bump it when the questions change
    validity_days: int
    questions: dict[str, dict[str, str]]  # question id -> {locale: text}
    statement: dict[str, str]  # by locale


FITNESS_FORM = HealthForm(
    key="fitness-v1",
    validity_days=365,
    questions={
        "heart": {
            "he": "האם רופא אמר לך שיש לך מחלת לב או לחץ דם גבוה?",
            "en": "Has a doctor ever said you have a heart condition or high blood pressure?",
        },
        "chest_pain": {
            "he": "האם את/ה חש/ה כאבים בחזה במנוחה, בפעילות יומיומית או בפעילות גופנית?",
            "en": "Do you feel pain in your chest at rest, during daily activities or exercise?",
        },
        "dizziness": {
            "he": "האם את/ה מאבד/ת שיווי משקל בגלל סחרחורת, או איבדת הכרה ב-12 החודשים האחרונים?",
            "en": "Do you lose balance because of dizziness, or have you lost consciousness "
            "in the last 12 months?",
        },
        "chronic": {
            "he": "האם אובחנה אצלך מחלה כרונית אחרת (מלבד מחלת לב או לחץ דם גבוה)?",
            "en": "Have you been diagnosed with another chronic condition (other than heart "
            "disease or high blood pressure)?",
        },
        "medication": {
            "he": "האם את/ה נוטל/ת כעת תרופות מרשם למחלה כרונית?",
            "en": "Do you currently take prescribed medication for a chronic condition?",
        },
        "bone_joint": {
            "he": "האם יש לך בעיה בעצמות, במפרקים או ברקמות רכות שפעילות גופנית עלולה להחמיר?",
            "en": "Do you have a bone, joint or soft-tissue problem that physical activity "
            "could make worse?",
        },
        "pregnancy": {
            "he": "האם את בהיריון או שילדת בשלושת החודשים האחרונים?",
            "en": "Are you pregnant, or have you given birth in the last three months?",
        },
    },
    statement={
        "he": "אני מצהיר/ה שהתשובות שמסרתי נכונות ומלאות, ושאעדכן את הסטודיו אם יחול שינוי "
        "במצב בריאותי.",
        "en": "I declare that my answers are true and complete, and I will tell the studio if "
        "my health changes.",
    },
)

FORMS: dict[str, HealthForm] = {"fitness": FITNESS_FORM}
