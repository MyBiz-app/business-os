"""Which tables hold a client's personal data, and what a privacy request does with each.

A client's export and erasure (app/api/privacy.py) must cover every table with a `client_id`.
A new table that is not listed here fails tests/test_privacy.py, so nobody can add client data
without deciding how it is exported and erased.

`export` is the key in the client's export document; `erase` is what erasure does with it:
deleted (the rows go), cleared (the row stays, personal fields are emptied) or kept (a
commercial or legal record the business must keep; see the note)."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ClientTable:
    export: str
    erase: Literal["deleted", "cleared", "kept"]
    note: str = ""


CLIENT_TABLES: dict[str, ClientTable] = {
    "announcement_deliveries": ClientTable("announcements_received", "deleted"),
    "bookings": ClientTable("bookings", "kept", "history; upcoming ones are cancelled"),
    "checkouts": ClientTable("checkouts", "kept", "payment records"),
    "client_addresses": ClientTable("addresses", "deleted"),
    "client_documents": ClientTable("documents", "deleted", "the files go from storage too"),
    "client_locations": ClientTable("branches", "deleted"),
    "client_notes": ClientTable("visit_notes", "deleted"),
    "client_social": ClientTable("friends_profile", "deleted"),
    "consent_events": ClientTable(
        "marketing_consent_history",
        "kept",
        "proof that ads were allowed; address and device cleared",
    ),
    "dependents": ClientTable("dependents", "deleted"),
    "entitlements": ClientTable("plans", "kept", "commercial history; freeze reasons cleared"),
    "health_declarations": ClientTable("health_declarations", "deleted"),
    "issued_documents": ClientTable("issued_documents", "kept", "tax documents, kept 7 years"),
    "leads": ClientTable("leads", "deleted"),
    "messages": ClientTable("messages", "deleted"),
    "notifications": ClientTable("notifications", "deleted"),
    "payments": ClientTable("payments", "kept", "accounting records"),
    "person_identities": ClientTable("identity_documents", "deleted"),
    "quotes": ClientTable("quotes", "kept", "commercial records; accepting name cleared"),
    "receipts": ClientTable("receipts", "kept", "accounting records; name and email cleared"),
    "retainers": ClientTable("retainer", "kept", "billing terms, no personal data"),
    "freeze_requests": ClientTable("freeze_requests", "kept", "membership history"),
    "reviews": ClientTable("reviews", "cleared", "the rating stays, the comment goes"),
    "time_entries": ClientTable("time_entries", "kept", "billing records"),
    "waitlist_offers": ClientTable("waitlist_offers", "deleted"),
    "waitlist_requests": ClientTable("waitlist_requests", "deleted"),
    "whatsapp_conversations": ClientTable("whatsapp_ai_conversations", "deleted"),
    "whatsapp_offers": ClientTable("whatsapp_offers", "deleted"),
}

# Tables a business export leaves out: secrets of outside services, sign-in tokens and the
# export files themselves. Binary columns (files, logos) are not written to CSV; the files are
# added to the archive as files.
BUSINESS_EXPORT_SKIP = frozenset(
    {"data_exports", "tenant_integrations", "social_accounts", "social_pending", "support_grants"}
)
# Column names that hold a secret, a token or an encrypted value, in any exported table.
SECRET_COLUMN_PARTS = ("token", "secret", "password", "api_key", "encrypted", "_hash")
