"""R19 live AI simulation: one command that measures what real questions cost on the configured
provider (credits per question kind, latency, errors) and prints a Markdown report.

    uv run python -m app.ai.live_sim                      # demo provider: free, report shape
    AI_LIVE_SIM_APPROVED=yes uv run python -m app.ai.live_sim --approved --max-usd 2

It never runs against a paid provider unless the owner approved it: both the environment variable
and the flag are required, the budget cap is enforced after every call, and it needs no passwords
(it talks to the model directly, not to a user's account). Running it costs money; see
docs/deploy/go-live-checklist.md (Switching on a live AI provider)."""

import argparse
import os
import statistics
import sys
import time
from dataclasses import dataclass

from app.ai.gateway import (
    LLMProvider,
    LLMResponse,
    ProviderBusy,
    ProviderUnavailable,
    credits,
    get_provider,
)

SYSTEM = (
    "You are the assistant of a small business. Answer briefly and concretely. You have no "
    "business data in this test: say what you would look at, in two or three sentences."
)

# kind -> (use the strong model, questions)
BANK: dict[str, tuple[bool, tuple[str, ...]]] = {
    "light": (
        False,
        (
            "What time do we open on Sundays?",
            "Write a one-line welcome message for a new client.",
            "Which clients usually cancel late?",
            "Give me a short reminder text for tomorrow's appointments.",
            "How do I add a second branch?",
        ),
    ),
    "regular": (
        False,
        (
            "Who has not visited in the last 30 days, and how should I win them back?",
            "Summarize this week's bookings and say what stands out.",
            "Draft a reply to a client asking for a refund on an unused pass.",
            "Suggest three ways to fill the empty morning slots.",
            "Which plans should I promote this month and why?",
        ),
    ),
    "heavy": (
        True,
        (
            "Plan next month's staff schedule for three branches with uneven demand.",
            "Compare revenue, attendance and cancellations across branches and recommend actions.",
            "Draft a cancellation policy for a studio with weekly plans, including exceptions.",
            "Build a 30-day win-back campaign for lapsed members with weekly message drafts.",
            "Review our pricing against attendance and propose a change with the expected effect.",
        ),
    ),
}


class Offline:
    """Stands in for the demo provider (which needs a business's tools): free, for a dry run."""

    model = "demo"

    def create(self, system: str, messages: list, tools: list, strong: bool = False) -> LLMResponse:
        return LLMResponse([{"type": "text", "text": "Offline dry run."}], "end_turn", self.model)


@dataclass
class Row:
    kind: str
    credits: float
    seconds: float
    error: str | None


def questions(total: int) -> list[tuple[str, bool, str]]:
    flat = [(kind, strong, q) for kind, (strong, qs) in BANK.items() for q in qs]
    return [flat[i % len(flat)] for i in range(total)]


def run(provider: LLMProvider, total: int, max_credits: float) -> tuple[list[Row], bool]:
    rows: list[Row] = []
    spent = 0.0
    for kind, strong, question in questions(total):
        started = time.monotonic()
        cost, error = 0.0, None
        try:
            response = provider.create(
                SYSTEM,
                [{"role": "user", "content": [{"type": "text", "text": question}]}],
                [],
                strong,
            )
            cost = credits(response.model, response.usage)
        except (ProviderBusy, ProviderUnavailable) as failure:
            error = type(failure).__name__
        spent += cost
        rows.append(Row(kind, cost, time.monotonic() - started, error))
        if spent >= max_credits:
            return rows, True  # stopped by the budget cap
    return rows, False


def report(rows: list[Row], model: str, stopped: bool) -> str:
    lines = [
        "# AI live simulation",
        "",
        f"Model: `{model}`. Calls: {len(rows)}. Total credits: {sum(r.credits for r in rows):.2f} "
        f"(1 credit = 1 US cent). Errors: {sum(1 for r in rows if r.error)}.",
    ]
    if stopped:
        lines.append("Stopped early: the budget cap was reached.")
    lines += [
        "",
        "| Kind | Calls | Avg credits | Max credits | Avg seconds | Errors |",
        "|---|---|---|---|---|---|",
    ]
    for kind in BANK:
        part = [r for r in rows if r.kind == kind]
        if not part:
            continue
        lines.append(
            f"| {kind} | {len(part)} | {statistics.fmean(r.credits for r in part):.3f} | "
            f"{max(r.credits for r in part):.3f} | "
            f"{statistics.fmean(r.seconds for r in part):.2f} | "
            f"{sum(1 for r in part if r.error)} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--questions", type=int, default=60)
    parser.add_argument("--max-usd", type=float, default=2.0, help="stop when this much is spent")
    parser.add_argument("--approved", action="store_true", help="the owner approved a paid run")
    parser.add_argument("--out", help="also write the report to this file")
    args = parser.parse_args(argv)

    provider = get_provider()
    if provider is None:
        print("No AI provider is set up.", file=sys.stderr)
        return 2
    paid = provider.model != "demo"
    if not paid:
        provider = Offline()
    if paid and not (args.approved and os.environ.get("AI_LIVE_SIM_APPROVED") == "yes"):
        print(
            f"Refusing to spend money on {provider.model}: needs --approved and "
            "AI_LIVE_SIM_APPROVED=yes (the owner's go).",
            file=sys.stderr,
        )
        return 3
    rows, stopped = run(provider, args.questions, args.max_usd * 100)
    text = report(rows, provider.model, stopped)
    print(text)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(text)
    return 1 if any(r.error for r in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
