"""Demo data: businesses with branches and months of realistic history, for any industry.

    uv run python -m app.seed --owner-email you@example.com [--demo studio|owner]
        [--owner-name "..."] [--replace] [--months 3] [--seed 7]

The owner must have signed up once (so their profile exists). The script creates businesses
owned by them, each with branches, services and plans from its industry (or its own), staff
per branch, a weekly timetable for classes and booked appointments, clients with a home branch,
plans sold over time (simulated payments) and bookings with attendance, no-shows, late
cancellations and waitlists. Staff are demo profiles that cannot sign in.

It writes with the migration (owner) connection, so it is for local and staging use only.
Everything is generated from --seed, so the same arguments produce the same studio.

The package splits the generator by area: `common` (names and the demos' businesses),
`business` (one business and its history), `industries` (what some industries add),
`activity` (reviews, messages, reservations, leads), `demos` and `platform`.
"""

import argparse
import random

from sqlalchemy import create_engine

from app.core.config import get_settings
from app.seed.business import seed
from app.seed.common import (
    AC_COMPANY,
    ACCOUNTING_FIRM,
    DEMOS,
    GROOMING_SALON,
    PADEL_CLUB,
    PHOTO_STUDIO,
    BranchSpec,
    BusinessSpec,
)
from app.seed.demos import seed_demo
from app.seed.platform import seed_platform

__all__ = [
    "ACCOUNTING_FIRM",
    "AC_COMPANY",
    "DEMOS",
    "GROOMING_SALON",
    "PADEL_CLUB",
    "PHOTO_STUDIO",
    "BranchSpec",
    "BusinessSpec",
    "main",
    "seed",
    "seed_demo",
    "seed_platform",
]


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m app.seed", description=__doc__.split("\n\n")[0]
    )
    parser.add_argument("--owner-email", required=True)
    parser.add_argument(
        "--demo",
        default="studio",
        choices=sorted(DEMOS),
        help="studio: one fitness studio; club: a padel club renting courts by the hour; "
        "pets: a pet grooming salon with owners and their pets; "
        "jobs: an air-conditioning company with on-site jobs at clients' addresses; "
        "events: a photography studio with quotes, deposits and events; "
        "office: an accounting firm with retainers, time, bills and documents; "
        "owner: a pilates chain with five branches and a barbershop with three; "
        "platform: the owner email becomes a MyBiz team owner and the "
        "platform gets small businesses, invoices and requests",
    )
    parser.add_argument("--owner-name", default=None, help="Sets the owner's display name")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Remove the owner's earlier copies of the demo businesses first",
    )
    parser.add_argument("--months", type=int, default=3, choices=range(1, 13))
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--database-url", default=None, help="Defaults to API_DATABASE_URL")
    args = parser.parse_args()

    engine = create_engine(args.database_url or get_settings().database_url)
    with engine.begin() as conn:
        if args.demo == "platform":
            seed_platform(
                conn,
                args.owner_email,
                args.months,
                random.Random(args.seed),
                staff_name=args.owner_name,
                replace=args.replace,
            )
            return
        seed_demo(
            conn,
            args.owner_email,
            args.demo,
            args.months,
            random.Random(args.seed),
            owner_name=args.owner_name,
            replace=args.replace,
        )
