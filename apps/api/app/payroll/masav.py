"""The bank transfer file for a month's net pay, in the Masav layout (round 6, P5).

The file is only generated: it is downloaded by the owner and uploaded to the bank's own site by
hand. Nothing here talks to a bank. Records are 128 characters, one per line, in code page 862
(the Hebrew DOS page the banks read). The layout follows the commonly published Masav record
description (header K, one record 1 per payee, total 5, closing line of nines); the bank's own
test upload is the final check before the first real use."""

from dataclasses import dataclass
from datetime import date

WIDTH = 128


@dataclass(frozen=True)
class Payee:
    name: str
    id_number: str
    bank_code: str
    branch: str
    account: str
    amount_minor: int
    reference: str = ""


@dataclass(frozen=True)
class Sender:
    institution_code: str  # 8 digits, given by Masav to the business
    sending_code: str  # 5 digits
    name: str


def _digits(value: str, width: int) -> str:
    return value.strip().rjust(width, "0")[-width:]


def _text(value: str, width: int) -> str:
    return value.strip()[:width].ljust(width)


def _record(parts: list[str]) -> str:
    line = "".join(parts)
    if len(line) > WIDTH:
        raise ValueError("record too long")
    return line.ljust(WIDTH)


def header(sender: Sender, pay_date: date, created: date) -> str:
    return _record(
        [
            "K",
            _digits(sender.institution_code, 8),
            "00",
            f"{pay_date:%y%m%d}",
            "0",
            "001",
            "0",
            f"{created:%y%m%d}",
            _digits(sender.sending_code, 5),
            "000000",
            _text(sender.name, 30),
            " " * 56,
            "KOT",
        ]
    )


def detail(sender: Sender, payee: Payee, period: date) -> str:
    return _record(
        [
            "1",
            _digits(sender.institution_code, 8),
            "00",
            "000000",
            _digits(payee.bank_code, 2),
            _digits(payee.branch, 3),
            "0000",
            _digits(payee.account, 9),
            "0",
            _digits(payee.id_number, 9),
            _text(payee.name, 16),
            _digits(str(payee.amount_minor), 13),
            _text(payee.reference, 20),
            f"{period:%y%m}{period:%y%m}",
            "000",
            "006",
            " " * 18,
            "  ",
        ]
    )


def total(sender: Sender, pay_date: date, payees: list[Payee]) -> str:
    credit = sum(p.amount_minor for p in payees)
    return _record(
        [
            "5",
            _digits(sender.institution_code, 8),
            "00",
            f"{pay_date:%y%m%d}",
            "0",
            "001",
            _digits("0", 15),
            _digits(str(credit), 15),
            _digits("0", 7),
            _digits(str(len(payees)), 7),
        ]
    )


def build(
    sender: Sender, pay_date: date, created: date, period: date, payees: list[Payee]
) -> bytes:
    """The whole file. Payees with nothing to pay must be left out by the caller."""
    lines = [header(sender, pay_date, created)]
    lines += [detail(sender, payee, period) for payee in payees]
    lines.append(total(sender, pay_date, payees))
    lines.append("9" * WIDTH)
    return ("\r\n".join(lines) + "\r\n").encode("cp862", errors="replace")
