"""Local e2e only: the real API with a scripted model instead of Claude (no API key, no cost).

    cd apps/api && PYTHONPATH=../../e2e:. uv run uvicorn fake_ai_api:app --port 8000
"""
import datetime as dt, json
from app.ai.gateway import LLMResponse, Usage, get_provider
from app.main import create_app

def text(t): return LLMResponse([{"type": "text", "text": t}], "end_turn", "claude-opus-5-5", Usage(500, 80))
def tool(name, args): return LLMResponse([{"type": "tool_use", "id": f"toolu_{name}_{dt.datetime.now().timestamp()}", "name": name, "input": args}], "tool_use", "claude-opus-5-5", Usage(500, 40))

class Fake:
    model = "claude-opus-5-5"
    def create(self, system, messages, tools):
        question = next(b["text"] for b in reversed(messages) if b["role"] == "user" and isinstance(b["content"], list) and b["content"][-1].get("type") == "text" for b in [b["content"][-1]] if not b["text"].startswith("<context>"))
        last = messages[-1]["content"][-1]
        result = json.loads(last["content"]) if last.get("type") == "tool_result" else None
        today = dt.date.today()
        if "רשום" in question or "book" in question.lower():
            if result is None:
                return tool("list_sessions", {"start_date": (today + dt.timedelta(days=1)).isoformat(), "days": 1})
            if "sessions" in result:
                self.session = result["sessions"][0]["id"]
                return tool("find_clients", {"query": "כהן"})
            if "clients" in result:
                return tool("book_client", {"session_id": self.session, "client_id": result["clients"][0]["id"]})
            return text("הכנתי את הרישום. אשרו אותו בכרטיס למטה.")
        if result is None:
            return tool("get_metrics", {"metrics": ["revenue", "occupancy"], "start_date": (today - dt.timedelta(days=30)).isoformat(), "end_date": (today - dt.timedelta(days=1)).isoformat()})
        m = {x["metric"]: x for x in result["metrics"]}
        occupancy = m["occupancy"]["value"]
        occupancy_text = "אין עדיין נתונים" if occupancy is None else f"{occupancy:.0f}%"
        return text(f"ב-30 הימים האחרונים:\n- הכנסות: ₪{(m['revenue']['value'] or 0)/100:,.0f}\n- תפוסה: {occupancy_text}")

app = create_app()
app.dependency_overrides[get_provider] = lambda: Fake()
