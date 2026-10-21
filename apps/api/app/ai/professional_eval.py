"""The test set of the legal and accountant agents (slice C3b): 40 questions with what a good
answer must contain, and a scorer for the answers of the real agent.

Run it after the library or the model changes: `run(ask)` takes a function that asks the real
agent one question and returns the answer text. It costs a few cents per question, and the console
AI budget is $0 until go-live, so it is not wired to a button yet and never runs in CI; the tests
check the set and the scoring with a scripted agent.

An answer passes when every group of `must` has at least one of its words in the answer and the
"not advice" line is there. The words are a first filter that a lawyer or an accountant reads
over: the expected answers are drafts until they approve them."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.ai import professional

SET = Path(__file__).parent / "eval_sets" / "professional.json"
KINDS = ("fact", "draft", "limit")


@dataclass(frozen=True)
class Result:
    id: str
    passed: bool
    missing: list[list[str]]
    notice: bool
    answer: str


def questions(agent: str | None = None) -> list[dict[str, Any]]:
    rows = json.loads(SET.read_text(encoding="utf-8"))
    return [q for q in rows if agent in (None, q["agent"])]


def score(question: dict[str, Any], answer: str) -> Result:
    lowered = answer.lower()
    missing = [g for g in question["must"] if not any(w.lower() in lowered for w in g)]
    notice = professional.notice_for(question["agent"], question["question"]) in answer
    return Result(question["id"], not missing and notice, missing, notice, answer)


def summary(results: list[Result]) -> dict[str, Any]:
    passed = sum(r.passed for r in results)
    return {
        "questions": len(results),
        "passed": passed,
        "score": round(100 * passed / len(results)) if results else 0,
        "failed": [r.id for r in results if not r.passed],
    }


def run(
    ask: Any, agent: str | None = None, limit: int | None = None
) -> tuple[list[Result], dict[str, Any]]:
    """Asks each question with `ask(agent, question_text) -> answer_text` and scores the answers."""
    results = [score(q, ask(q["agent"], q["question"])) for q in questions(agent)[:limit]]
    return results, summary(results)
