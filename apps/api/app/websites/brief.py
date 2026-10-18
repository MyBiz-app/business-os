"""The wizard's answers ("tell us about your website"), saved as a draft after each step.

Every field is optional while the brief is a draft; `missing_for_submit` names what must be
filled before it can be sent."""

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Goal = Literal["leads", "bookings", "showcase", "sell"]
Section = Literal[
    "hero",
    "services",
    "gallery",
    "team",
    "testimonials",
    "faq",
    "location",
    "contact",
    "booking",
    "whatsapp",
]
Style = Literal["clean", "luxury", "warm", "vibrant"]
Motion = Literal["none", "subtle", "rich"]
Language = Literal["he", "en"]
Hex = Annotated[str, StringConstraints(pattern=r"^#[0-9a-fA-F]{6}$")]
Text = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1200)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
Url = Annotated[str, StringConstraints(pattern=r"^https?://[^\s]+$", max_length=300)]


class ImageNote(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file_id: UUID
    note: ShortText | None = None


class Inspiration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: Url
    likes: ShortText | None = None


class Brief(BaseModel):
    """Eight steps, in the wizard's order."""

    model_config = ConfigDict(extra="forbid")

    # 1. The goal
    goals: list[Goal] = Field(default_factory=list, max_length=4)
    main_action: ShortText | None = None
    # 2. The business
    unique: Text | None = None
    audience: ShortText | None = None
    area: ShortText | None = None
    # 3. Sections
    sections: list[Section] = Field(default_factory=list, max_length=10)
    # 4. Branding
    no_logo: bool = False
    logo_file_id: UUID | None = None
    colors_from_brand: bool = True
    colors: list[Hex] = Field(default_factory=list, max_length=4)
    style: Style | None = None
    font: ShortText | None = None
    # 5. Motion
    motion: Motion | None = None
    # 6. Images
    images: list[ImageNote] = Field(default_factory=list, max_length=20)
    no_good_photos: bool = False
    # 7. Inspiration and copy
    inspiration: list[Inspiration] = Field(default_factory=list, max_length=3)
    copy_by: Literal["me", "you"] | None = None
    # 8. Domain and languages
    domain: Literal["have", "buy", "temporary"] | None = None
    domain_name: ShortText | None = None
    languages: list[Language] = Field(default_factory=list, max_length=2)
    due_date: date | None = None


def missing_for_submit(brief: Brief, *, with_system: bool) -> list[str]:
    """The answers a submitted brief needs; the rest are optional."""
    missing: list[str] = []
    if not brief.goals:
        missing.append("goals")
    if not brief.sections:
        missing.append("sections")
    elif "booking" in brief.sections and not with_system:
        missing.append("booking_needs_system")
    if brief.style is None:
        missing.append("style")
    if brief.motion is None:
        missing.append("motion")
    if brief.copy_by is None:
        missing.append("copy_by")
    if brief.domain is None:
        missing.append("domain")
    elif brief.domain == "have" and not brief.domain_name:
        missing.append("domain_name")
    if not brief.languages:
        missing.append("languages")
    return missing
