"""Profile pictures of the people who work in businesses (never of a business's clients).

A picture is private: the person reads their own, and members of a business read the pictures
of the business's team (row-level security on `app.users` allows exactly that)."""

from uuid import UUID

from fastapi import APIRouter, Response, UploadFile
from sqlalchemy import text

from app.api.common import not_found
from app.api.deps import SessionDep, TenantDep, UserDep
from app.api.routes import ensure_profile, get_me
from app.api.schemas import Me
from app.api.settings import IMAGE_RESPONSES, MAX_LOGO_BYTES, image_response, read_image

router = APIRouter(tags=["account"])


@router.put("/me/avatar")
async def upload_avatar(file: UploadFile, user: UserDep, session: SessionDep) -> Me:
    data, content_type = await read_image(file, MAX_LOGO_BYTES)
    ensure_profile(session, user.id, user.email)
    session.execute(
        text("""
            UPDATE app.users
            SET avatar = :data, avatar_content_type = :content_type,
                avatar_updated_at = now(), updated_at = now()
            WHERE id = :id
        """),
        {"data": data, "content_type": content_type, "id": user.id},
    )
    return get_me(user, session)


@router.delete("/me/avatar")
def delete_avatar(user: UserDep, session: SessionDep) -> Me:
    session.execute(
        text("""
            UPDATE app.users
            SET avatar = NULL, avatar_content_type = NULL, avatar_updated_at = NULL,
                updated_at = now()
            WHERE id = :id
        """),
        {"id": user.id},
    )
    return get_me(user, session)


@router.get("/me/avatar", response_class=Response, responses=IMAGE_RESPONSES)
def get_own_avatar(user: UserDep, session: SessionDep) -> Response:
    return _avatar(session, user.id, "")


@router.get("/staff/{user_id}/avatar", response_class=Response, responses=IMAGE_RESPONSES)
def get_member_avatar(user_id: UUID, context: TenantDep) -> Response:
    """A team member's picture, for the business's own team."""
    return _avatar(
        context.session,
        user_id,
        """AND EXISTS (SELECT 1 FROM app.tenant_members m
                       WHERE m.tenant_id = app.current_tenant_id() AND m.user_id = u.id)""",
    )


def _avatar(session: SessionDep, user_id: UUID, condition: str) -> Response:
    row = session.execute(
        text(f"""
            SELECT u.avatar, u.avatar_content_type FROM app.users u
            WHERE u.id = :id AND u.avatar IS NOT NULL {condition}
        """),
        {"id": user_id},
    ).first()
    if row is None:
        raise not_found()
    return image_response(row.avatar, row.avatar_content_type)
