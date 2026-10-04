"""Demo mode for the assistant: answers common questions without a model (no API key, no cost).

It recognizes a few kinds of question by keywords (Hebrew and English), calls the same tools
the model would (so answers use the business's real data and permissions) and writes a short
answer from the results. Every answer says it comes from demo mode. With an API key the real
model replaces it (app/ai/gateway.py)."""

import datetime as dt
import json
import re
from typing import Any

from app.ai.gateway import LLMResponse, Usage

MODEL = "demo"

INTENTS: dict[str, tuple[str, ...]] = {
    "book": ("רשמ", "רשום", "תרשום", "להירשם", "book", "sign up", "enroll"),
    "inactive": ("לא הגיע", "לא הגיעו", "נעדר", "לפנות", "נטש", "inactive", "haven't come",
                 "not come", "at risk", "absent"),
    "sessions": ("היום", "מחר", "שיעור", "לוח", "today", "tomorrow", "class", "schedule"),
    "plans": ("מחיר", "מנוי", "כרטיסי", "מסלול", "price", "plan", "membership", "pass"),
    "metrics": ("הכנס", "כסף", "תפוס", "הגעות", "נתונים", "מספרים", "סיכום", "איך", "מצב",
                "revenue", "income", "occupancy", "attendance", "numbers", "summary", "how"),
}  # fmt: skip

TEXT = {
    "he": {
        "label": "🧪 מצב הדגמה (ללא AI אמיתי)",
        "help": (
            "אני העוזר במצב הדגמה. אפשר לשאול למשל:\n"
            "- איך העסק עובד החודש? (הכנסות, הגעות ותפוסה)\n"
            "- אילו שיעורים יש היום / מחר?\n"
            "- מי לא הגיע כבר שבועיים?\n"
            "- מה המחירים של המנויים?\n"
            "- תרשום את דנה לשיעור מחר\n"
            "כשיוגדר מפתח AI, אענה על כל שאלה."
        ),
        "metrics": "ב-30 הימים האחרונים:",
        "revenue": "הכנסות",
        "attendance": "הגעות",
        "occupancy": "תפוסה",
        "new_clients": "לקוחות חדשים",
        "vs": "לעומת {value} בתקופה הקודמת",
        "no_data": "אין עדיין נתונים",
        "sessions_today": "השיעורים היום:",
        "sessions_tomorrow": "השיעורים מחר:",
        "no_sessions": "אין שיעורים ביום הזה.",
        "cancelled": "בוטל",
        "inactive": "מתאמנים עם מנוי בתוקף שלא הגיעו 14 יום ומעלה:",
        "never": "עוד לא הגיעו",
        "last_visit": "ביקור אחרון",
        "no_inactive": "כל המתאמנים עם מנוי בתוקף הגיעו בשבועיים האחרונים.",
        "plans": "המנויים והכרטיסיות:",
        "entries": "{count} כניסות",
        "days": "{count} ימים",
        "book_who": "את מי לרשום? כתבו למשל: תרשום את דנה לשיעור מחר.",
        "book_none": 'לא מצאתי לקוח בשם "{name}".',
        "book_no_session": "אין שיעור פנוי מחר.",
        "book_ready": "הכנתי רישום של {name} ל{service} ב-{time}. אשרו אותו בכרטיס למטה.",
        "book_off": "רישום דרך העוזר זמין בחבילת AI Pro.",
    },
    "en": {
        "label": "🧪 Demo mode (no real AI)",
        "help": (
            "I'm the assistant in demo mode. Try asking:\n"
            "- How is the business doing this month? (revenue, attendance, occupancy)\n"
            "- Which classes are on today / tomorrow?\n"
            "- Who hasn't come in for two weeks?\n"
            "- What do the plans cost?\n"
            "- Book Dana into tomorrow's class\n"
            "With an AI key set up, I can answer anything."
        ),
        "metrics": "In the last 30 days:",
        "revenue": "Revenue",
        "attendance": "Attendance",
        "occupancy": "Occupancy",
        "new_clients": "New clients",
        "vs": "vs {value} the period before",
        "no_data": "no data yet",
        "sessions_today": "Today's classes:",
        "sessions_tomorrow": "Tomorrow's classes:",
        "no_sessions": "No classes on that day.",
        "cancelled": "cancelled",
        "inactive": "Members with a valid plan who haven't come in for 14+ days:",
        "never": "never came",
        "last_visit": "last visit",
        "no_inactive": "Every member with a valid plan came in during the last two weeks.",
        "plans": "Plans:",
        "entries": "{count} entries",
        "days": "{count} days",
        "book_who": "Whom should I book? For example: book Dana into tomorrow's class.",
        "book_none": 'I couldn\'t find a client named "{name}".',
        "book_no_session": "There is no open class tomorrow.",
        "book_ready": "I prepared booking {name} into {service} at {time}. Confirm it on the card.",
        "book_off": "Booking through the assistant comes with the AI Pro plan.",
    },
}


def _text(value: str) -> LLMResponse:
    return LLMResponse([{"type": "text", "text": value}], "end_turn", MODEL, Usage())


def _tool(name: str, args: dict[str, Any], step: int) -> LLMResponse:
    block = {"type": "tool_use", "id": f"demo_{name}_{step}", "name": name, "input": args}
    return LLMResponse([block], "tool_use", MODEL, Usage())


def _intent(question: str) -> str:
    lowered = question.lower()
    for intent, words in INTENTS.items():
        if any(word in lowered for word in words):
            return intent
    return "help"


def _booking_name(question: str) -> str | None:
    """The client's name in "תרשום את דנה ..." / "book Dana into ..."."""
    match = re.search(r"(?:את|book|enroll|sign up)\s+([^\s,.?!]+)", question, re.IGNORECASE)
    return match.group(1) if match else None


class DemoProvider:
    model = MODEL

    def create(
        self, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> LLMResponse:
        turn = self._current_turn(messages)
        question = next(
            block["text"]
            for block in turn[0]["content"]
            if block.get("type") == "text" and not block["text"].startswith("<context>")
        )
        context = next(
            block["text"]
            for block in turn[0]["content"]
            if block.get("type") == "text" and block["text"].startswith("<context>")
        )
        today = dt.date.fromisoformat(re.search(r"\d{4}-\d{2}-\d{2}", context).group(0))  # type: ignore[union-attr]
        currency = (re.search(r"currency ([A-Z]{3})", context) or [None, "ILS"])[1]
        locale = "he" if re.search(r"[֐-׿]", question) else "en"
        results = [
            json.loads(block["content"])
            for message in turn[1:]
            if message["role"] == "user"
            for block in message["content"]
            if block.get("type") == "tool_result"
        ]
        available = {tool["name"] for tool in tools}
        answer = self._answer(_intent(question), question, today, results, available, locale)
        if answer.stop_reason == "tool_use":
            return answer
        label = TEXT[locale]["label"]
        body = answer.content[0]["text"]
        return _text(f"{label}\n\n{self._money(body, currency, locale)}")

    @staticmethod
    def _current_turn(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """The messages since the user's latest question (with its context block)."""
        for index in range(len(messages) - 1, -1, -1):
            content = messages[index]["content"]
            if messages[index]["role"] == "user" and any(
                block.get("type") == "text" and block["text"].startswith("<context>Today is")
                for block in content
            ):
                return messages[index:]
        return messages

    @staticmethod
    def _money(body: str, currency: str, locale: str) -> str:
        def replace(match: re.Match[str]) -> str:
            amount = int(match.group(1)) / 100
            symbol = {"ILS": "₪", "USD": "$", "EUR": "€"}.get(currency, currency + " ")
            return f"{symbol}{amount:,.0f}"

        return re.sub(r"\{money:(\d+)\}", replace, body)

    def _answer(
        self,
        intent: str,
        question: str,
        today: dt.date,
        results: list[dict[str, Any]],
        available: set[str],
        locale: str,
    ) -> LLMResponse:
        t = TEXT[locale]
        step = len(results)
        if intent == "metrics" and "get_metrics" in available:
            if not results:
                return _tool(
                    "get_metrics",
                    {
                        "metrics": ["revenue", "attendance", "occupancy", "new_clients"],
                        "start_date": (today - dt.timedelta(days=30)).isoformat(),
                        "end_date": (today - dt.timedelta(days=1)).isoformat(),
                    },
                    step,
                )
            lines = [t["metrics"]]
            for metric in results[-1].get("metrics", []):
                lines.append(
                    f"- {t[metric['metric']]}: {self._value(metric, metric['value'], t)}"
                    + (
                        f" ({t['vs'].format(value=self._value(metric, metric['previous'], t))})"
                        if metric["previous"] is not None
                        else ""
                    )
                )
            return _text("\n".join(lines))

        if intent == "sessions" and "list_sessions" in available:
            tomorrow = "מחר" in question or "tomorrow" in question.lower()
            if not results:
                day = today + dt.timedelta(days=1 if tomorrow else 0)
                return _tool("list_sessions", {"start_date": day.isoformat(), "days": 1}, step)
            sessions = results[-1].get("sessions", [])
            if not sessions:
                return _text(t["no_sessions"])
            lines = [t["sessions_tomorrow" if tomorrow else "sessions_today"]]
            for s in sessions:
                state = f" · {t['cancelled']}" if s["status"] == "cancelled" else ""
                lines.append(
                    f"- {s['starts'][-5:]} {s['service']}: {s['booked']}/{s['capacity']}{state}"
                )
            return _text("\n".join(lines))

        if intent == "inactive" and "inactive_members" in available:
            if not results:
                return _tool("inactive_members", {"days": 14}, step)
            members = results[-1].get("members", [])
            if not members:
                return _text(t["no_inactive"])
            lines = [t["inactive"]]
            for m in members[:15]:
                visit = f"{t['last_visit']} {m['last_visit']}" if m["last_visit"] else t["never"]
                lines.append(f"- {m['name']} ({visit})")
            return _text("\n".join(lines))

        if intent == "plans" and "list_plans" in available:
            if not results:
                return _tool("list_plans", {}, step)
            lines = [t["plans"]]
            for p in results[-1].get("plans", []):
                extra = (
                    t["entries"].format(count=p["entries"])
                    if p["entries"]
                    else t["days"].format(count=p["validity_days"])
                )
                lines.append(f"- {p['name']}: {{money:{p['price_minor_units']}}} · {extra}")
            return _text("\n".join(lines))

        if intent == "book":
            return self._book(question, today, results, available, t)

        return _text(t["help"])

    @staticmethod
    def _value(metric: dict[str, Any], value: float | None, t: dict[str, str]) -> str:
        if value is None:
            return t["no_data"]
        if metric["unit"] == "money":
            return f"{{money:{round(value)}}}"
        if metric["unit"] == "percent":
            return f"{value:.0f}%"
        return f"{value:,.0f}"

    @staticmethod
    def _book(
        question: str,
        today: dt.date,
        results: list[dict[str, Any]],
        available: set[str],
        t: dict[str, str],
    ) -> LLMResponse:
        if "book_client" not in available:
            return _text(t["book_off"])
        name = _booking_name(question)
        if not name:
            return _text(t["book_who"])
        step = len(results)
        if step == 0:
            return _tool("find_clients", {"query": name}, step)
        clients = results[0].get("clients", [])
        if not clients:
            return _text(t["book_none"].format(name=name))
        if step == 1:
            tomorrow = (today + dt.timedelta(days=1)).isoformat()
            return _tool("list_sessions", {"start_date": tomorrow, "days": 1}, step)
        sessions = [s for s in results[1].get("sessions", []) if s["status"] != "cancelled"]
        open_sessions = [s for s in sessions if s["booked"] < s["capacity"]] or sessions
        if not open_sessions:
            return _text(t["book_no_session"])
        session = open_sessions[0]
        if step == 2:
            return _tool(
                "book_client", {"session_id": session["id"], "client_id": clients[0]["id"]}, step
            )
        return _text(
            t["book_ready"].format(
                name=clients[0]["name"], service=session["service"], time=session["starts"][-5:]
            )
        )
