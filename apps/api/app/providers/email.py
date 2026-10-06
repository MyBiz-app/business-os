"""Email: the senders in app/email.py, registered like every other provider."""

from email.utils import parseaddr

from app.email import LogSender, ResendSender, Sender, SmtpSender
from app.providers.registry import SettingField, register

FROM = SettingField("from", "From address (Name <address>)", required=False)


@register("email", "log", "Log only (nothing is sent)", builtin=True)
class LogEmail:
    def __new__(cls, settings: dict[str, str]) -> Sender:  # type: ignore[misc]
        return LogSender()


@register(
    "email", "resend", "Resend", fields=(SettingField("api_key", "API key", secret=True), FROM)
)
class ResendEmail:
    def __new__(cls, settings: dict[str, str]) -> Sender:  # type: ignore[misc]
        return ResendSender(settings["api_key"], settings.get("from", ""))


@register(
    "email",
    "smtp",
    "SMTP (Gmail, Outlook, any mail server)",
    fields=(
        SettingField("host", "Server"),
        SettingField("port", "Port", required=False),
        SettingField("username", "Username", required=False),
        SettingField("password", "Password", secret=True),
        FROM,
    ),
)
class SmtpEmail:
    def __new__(cls, settings: dict[str, str]) -> Sender:  # type: ignore[misc]
        sender = settings.get("from", "")
        return SmtpSender(
            settings["host"],
            int(settings.get("port") or 465),
            settings.get("username") or parseaddr(sender)[1],
            settings["password"],
            sender,
        )
