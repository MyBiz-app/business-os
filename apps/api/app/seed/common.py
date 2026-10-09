"""Shared building blocks of the demo data: names, the businesses each demo creates, and small
helpers."""

from dataclasses import dataclass, field
from datetime import date
from uuid import UUID

from sqlalchemy import Connection, text

TIME_ZONE = "Asia/Jerusalem"

SOURCES = ("walk_in", "referral", "instagram", "facebook", "google", "website")
SOURCE_WEIGHTS = (3, 4, 5, 2, 2, 1)
CLIENTS = 170
LEADS = 15  # the newest clients: interested, never bought

FIRST_NAMES = [
    "נועה",
    "מאיה",
    "תמר",
    "יעל",
    "שירה",
    "אביגיל",
    "רוני",
    "מיכל",
    "ליה",
    "הדר",
    "אלה",
    "עדי",
    "נטע",
    "גלי",
    "דנה",
    "אורי",
    "טל",
    "רותם",
    "שני",
    "ענבל",
    "קרן",
    "ליאת",
    "סיון",
    "הילה",
    "מורן",
    "איתי",
    "יונתן",
    "עומר",
    "אריאל",
    "דניאל",
    "נדב",
    "גיא",
    "עידו",
    "אסף",
    "רועי",
]
LAST_NAMES = [
    "כהן",
    "לוי",
    "מזרחי",
    "פרץ",
    "ביטון",
    "אברהם",
    "פרידמן",
    "אזולאי",
    "דהן",
    "אוחיון",
    "חדד",
    "גבאי",
    "שפירא",
    "קליין",
    "רוזן",
    "אשכנזי",
    "גולן",
    "ברק",
    "שלום",
    "יוסף",
]

# (name he, name en, minutes, capacity, color, popularity 0..1)
SERVICES = (
    ("פילאטיס מזרן", "Mat Pilates", 55, 12, "#6366f1", 0.85),
    ("פילאטיס מכשירים", "Reformer Pilates", 50, 6, "#ec4899", 0.95),
    ("יוגה פלואו", "Yoga Flow", 60, 15, "#10b981", 0.7),
    ("HIIT", "HIIT", 45, 14, "#f59e0b", 0.65),
    ("בר", "Barre", 50, 12, "#8b5cf6", 0.6),
)
INSTRUCTORS = (("מאיה", "רז"), ("אורן", "שגיא"), ("ליאור", "נחום"), ("שירן", "בן דוד"))

# Weekly timetable: (weekday 0=Mon..6=Sun, "HH:MM", service index, room index, instructor index)
TIMETABLE = (
    (6, "07:00", 0, 0, 0), (6, "09:00", 2, 0, 2), (6, "18:00", 1, 1, 1), (6, "19:15", 3, 0, 3),
    (0, "07:00", 1, 1, 1), (0, "08:30", 4, 0, 0), (0, "18:30", 0, 0, 2), (0, "19:30", 1, 1, 1),
    (1, "07:00", 3, 0, 3), (1, "09:30", 2, 0, 2), (1, "18:00", 1, 1, 0), (1, "19:15", 4, 0, 0),
    (2, "07:00", 0, 0, 0), (2, "12:00", 2, 0, 2), (2, "18:00", 1, 1, 1), (2, "19:15", 3, 0, 3),
    (3, "07:00", 1, 1, 1), (3, "09:00", 4, 0, 0), (3, "18:30", 0, 0, 2), (3, "19:30", 2, 0, 2),
    (4, "08:00", 1, 1, 1), (4, "09:30", 0, 0, 0), (4, "11:00", 2, 0, 2),
    (5, "09:00", 3, 0, 3), (5, "10:30", 2, 0, 2),
)  # fmt: skip


@dataclass
class Entitlement:
    id: UUID
    kind: str
    starts_on: date
    ends_on: date
    credits: int | None
    used: int = 0

    def usable(self, day: date) -> bool:
        has_credit = self.credits is None or self.used < self.credits
        return self.starts_on <= day <= self.ends_on and has_credit


@dataclass
class Client:
    id: UUID
    joined: date
    churns_on: date | None
    habit: float  # chance to book any fitting class
    favorite_hours: set[int]
    entitlements: list[Entitlement] = field(default_factory=list)

    def plan_on(self, day: date) -> Entitlement | None:
        usable = [e for e in self.entitlements if e.usable(day)]
        usable.sort(key=lambda e: (e.credits is not None, e.ends_on))
        return usable[0] if usable else None


def _insert(conn: Connection, sql: str, rows: list[dict]) -> None:
    if rows:
        conn.execute(text(sql), rows)


@dataclass(frozen=True)
class BranchSpec:
    name: str
    address: str


@dataclass(frozen=True)
class BusinessSpec:
    """One demo business: its industry (a catalog key), branches and size. Services, plans and
    client details come from the industry catalog unless the spec brings its own."""

    name: str
    vertical: str
    color: str
    billing_name: str
    branches: tuple[BranchSpec, ...]
    clients: int = CLIENTS
    staff_per_branch: int = 2
    # The classic studio keeps its hand-made services and timetable (tests rely on it).
    custom_services: tuple[tuple[str, str, int, int, str, float], ...] | None = None
    timetable: tuple[tuple[int, str, int, int, int], ...] | None = None


STUDIO = BusinessSpec(
    name="סטודיו פלואו (דמו)",
    vertical="fitness",
    color="#0f766e",
    billing_name="סטודיו פלואו בע״מ",
    branches=(BranchSpec("תל אביב - פלורנטין", "הרצל 120, תל אביב"),),
    staff_per_branch=len(INSTRUCTORS),
    custom_services=SERVICES,
    timetable=TIMETABLE,
)

# The owner's demo (decision T78): a chain with five branches and a barbershop with three.
PILATES_CHAIN = BusinessSpec(
    name="פילאטיס פלוס",
    vertical="pilates",
    color="#7c3aed",
    billing_name="פילאטיס פלוס בע״מ",
    branches=(
        BranchSpec("תל אביב - רוטשילד", "שדרות רוטשילד 45, תל אביב"),
        BranchSpec("רמת גן - הבורסה", "ז׳בוטינסקי 7, רמת גן"),
        BranchSpec("הרצליה פיתוח", "אבא אבן 10, הרצליה"),
        BranchSpec("ירושלים - המושבה הגרמנית", "עמק רפאים 30, ירושלים"),
        BranchSpec("חיפה - כרמל", "שדרות הנשיא 120, חיפה"),
    ),
    clients=420,
    staff_per_branch=3,
)
BARBERSHOP = BusinessSpec(
    name="בלייד ברברס",
    vertical="barbershop",
    color="#b45309",
    billing_name="בלייד ברברס בע״מ",
    branches=(
        BranchSpec("תל אביב - דיזנגוף", "דיזנגוף 200, תל אביב"),
        BranchSpec("גבעתיים", "כצנלסון 60, גבעתיים"),
        BranchSpec("ראשון לציון", "רוטשילד 30, ראשון לציון"),
    ),
    clients=300,
    staff_per_branch=3,
)
PADEL_CLUB = BusinessSpec(
    name="פאדל פוינט (דמו)",
    vertical="padel_tennis",
    color="#4d7c0f",
    billing_name="פאדל פוינט בע״מ",
    branches=(BranchSpec("הרצליה", "הנדיב 71, הרצליה"),),
    clients=140,
    staff_per_branch=1,
)
GROOMING_SALON = BusinessSpec(
    name="כפות שמחות (דמו)",
    vertical="pet_grooming",
    color="#c2410c",
    billing_name="כפות שמחות בע״מ",
    branches=(BranchSpec("רמת השרון", "סוקולוב 40, רמת השרון"),),
    clients=160,
    staff_per_branch=2,
)
AC_COMPANY = BusinessSpec(
    name="אוויר קריר (דמו)",
    vertical="ac_technicians",
    color="#0369a1",
    billing_name="אוויר קריר שירותי מיזוג בע״מ",
    branches=(BranchSpec("מרכז", "המלאכה 8, ראש העין"),),
    clients=150,
    staff_per_branch=3,
)
PHOTO_STUDIO = BusinessSpec(
    name="סטודיו שעת זהב (דמו)",
    vertical="photographers",
    color="#a21caf",
    billing_name="שעת זהב צילום בע״מ",
    branches=(BranchSpec("יפו", "יפת 30, תל אביב-יפו"),),
    clients=120,
    staff_per_branch=2,
)
ACCOUNTING_FIRM = BusinessSpec(
    name="לוי ושות׳ רואי חשבון (דמו)",
    vertical="accountants",
    color="#0e7490",
    billing_name="לוי ושות׳ רואי חשבון",
    branches=(BranchSpec("רמת גן", "ז׳בוטינסקי 35, רמת גן"),),
    clients=60,
    staff_per_branch=3,
)
DEMOS: dict[str, tuple[BusinessSpec, ...]] = {
    "studio": (STUDIO,),
    "club": (PADEL_CLUB,),
    "pets": (GROOMING_SALON,),
    "jobs": (AC_COMPANY,),
    "events": (PHOTO_STUDIO,),
    "office": (ACCOUNTING_FIRM,),
    "owner": (PILATES_CHAIN, BARBERSHOP),
    "platform": (),  # MyBiz's own view: many small businesses (PLATFORM_BUSINESSES)
}

# The platform demo: small businesses of several industries, each with a fictitious owner, so
# the MyBiz console has businesses, invoices and requests to show.
PLATFORM_BUSINESSES: tuple[tuple[BusinessSpec, str], ...] = tuple(
    (
        BusinessSpec(
            name=name,
            vertical=vertical,
            color=color,
            billing_name=f"{name} בע״מ",
            branches=(BranchSpec(branch, address),),
            clients=clients,
            staff_per_branch=2,
        ),
        owner,
    )
    for name, vertical, color, branch, address, clients, owner in (
        ("יוגה בגבעה", "yoga", "#059669", "זכרון יעקב", "המייסדים 40, זכרון יעקב", 90, "מיכל לוי"),
        (
            "קרוספיט צפון",
            "crossfit",
            "#dc2626",
            "קריית ביאליק",
            "דרך עכו 210, קריית ביאליק",
            120,
            "רון אברהם",
        ),
        (
            "פיזיו פלוס",
            "physiotherapy",
            "#0284c7",
            "פתח תקווה",
            "ז׳בוטינסקי 100, פתח תקווה",
            70,
            "ד״ר נועה שגיא",
        ),
        ("סטודיו מחול רונה", "dance", "#db2777", "רחובות", "הרצל 150, רחובות", 110, "רונה כהן"),
        ("מספרת הדר", "hair_salon", "#a16207", "באר שבע", "רגר 30, באר שבע", 80, "הדר מזרחי"),
        ("מוסך המומחים", "garage", "#475569", "חולון", "המלאכה 12, חולון", 60, "יוסי ביטון"),
    )
)
PLATFORM_REQUESTS = (
    (
        "שירה גולן",
        "shira@example.invalid",
        "סטודיו שירה",
        "pilates",
        "מעוניינת להעביר את הסטודיו מהמערכת הקודמת, אפשר עזרה בייבוא לקוחות?",
        "new",
    ),
    (
        "עמית ברק",
        "amit@example.invalid",
        "ברק כושר",
        "gym",
        "יש לנו שלושה סניפים, כמה עולה סניף נוסף?",
        "new",
    ),
    (
        "ליאת חן",
        "liat@example.invalid",
        "קליניקת ליאת",
        "aesthetics",
        "רוצה לשמוע על אפליקציית הלקוחות עם הלוגו שלנו",
        "in_progress",
    ),
    (
        "דני פרץ",
        "dani@example.invalid",
        "פרץ גראז׳",
        "garage",
        "שאלה על חשבוניות ללקוחות עסקיים",
        "done",
    ),
)

# Staff hours for appointments: weekday (0 = Monday) -> (opens, closes); Friday until 14:00.
WORK_HOURS = {6: (9, 19), 0: (9, 19), 1: (9, 19), 2: (9, 19), 3: (9, 19), 4: (9, 14)}
CLASS_HOURS = ("07:00", "08:30", "09:30", "12:00", "17:30", "18:30", "19:30", "20:30")
GENERIC_NOTES = (
    "מרוצה מאוד מהתוצאה",
    "ביקש/ה תור קבוע כל חודש",
    "מעדיף/ה שעות בוקר",
    "להזכיר יום לפני התור הבא",
    "הגיע/ה עם חבר/ה, אולי לקוח/ה חדש/ה",
)
GENERIC_REVIEWS = {
    5: ("שירות מעולה!", "מקצועיים ונעימים", "בדיוק מה שרציתי"),
    4: ("טוב מאוד, חיכיתי קצת", "נהניתי", "אחלה אווירה"),
    3: ("היה בסדר", "קצת יקר"),
    2: ("התחיל באיחור", "לא בדיוק מה שביקשתי"),
    1: ("התור בוטל ברגע האחרון",),
}


def profile_id(conn: Connection, email: str) -> UUID | None:
    """The person's profile; created from their sign-up (Supabase auth) when they have not
    used the app yet, e.g. when they could not log in before their email was confirmed."""
    if conn.execute(text("SELECT to_regclass('auth.users') IS NOT NULL")).scalar():
        conn.execute(
            text("""
                INSERT INTO app.users (id, email)
                SELECT id, lower(email) FROM auth.users WHERE lower(email) = lower(:email)
                ON CONFLICT DO NOTHING
            """),
            {"email": email},
        )
    return conn.execute(
        text("SELECT id FROM app.users WHERE lower(email) = lower(:email)"), {"email": email}
    ).scalar()
