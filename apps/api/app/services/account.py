from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.review import Review
from app.models.user import User
from app.models.vocab_item import VocabItem
from app.services.google_identity import GoogleIdentity

STARTER_VOCAB = [
    {"token": "friend", "language": "en", "definition": "a person you like and play with"},
    {"token": "hungry", "language": "en", "definition": "wanting to eat food"},
    {"token": "happy", "language": "en", "definition": "feeling good and smiling"},
    {"token": "morning", "language": "en", "definition": "the early part of the day"},
    {"token": "family", "language": "en", "definition": "parents, brothers and sisters"},
    {"token": "school", "language": "en", "definition": "a place where children learn"},
    {"token": "play", "language": "en", "definition": "to have fun with toys or games"},
    {"token": "animal", "language": "en", "definition": "a living creature like a dog or cat"},
    {"token": "rain", "language": "en", "definition": "water that falls from clouds"},
    {"token": "color", "language": "en", "definition": "red, blue, green and other shades"},
    {"token": "night", "language": "en", "definition": "the dark time between sunset and sunrise"},
    {"token": "story", "language": "en", "definition": "a tale that you read or tell"},
]


async def _heal_starter_vocab_definitions(session: AsyncSession) -> int:
    healed = 0
    for entry in STARTER_VOCAB:
        canonical = entry.get("definition", "")
        if not canonical:
            continue
        item = (
            await session.execute(
                select(VocabItem).where(
                    VocabItem.token == entry["token"],
                    VocabItem.language == entry["language"],
                )
            )
        ).scalar_one_or_none()
        if item is not None and not item.definition:
            item.definition = canonical
            healed += 1
    if healed:
        await session.commit()
    return healed


async def _seed_starter_vocab(session: AsyncSession, user: User) -> int:
    created = 0
    now = datetime.now(UTC)
    for entry in STARTER_VOCAB:
        token = entry["token"]
        language = entry["language"]
        canonical_definition = entry.get("definition", "")
        existing = (
            await session.execute(
                select(VocabItem).where(VocabItem.token == token, VocabItem.language == language)
            )
        ).scalar_one_or_none()
        if existing is not None:
            item = existing
            if not item.definition and canonical_definition:
                item.definition = canonical_definition
        else:
            item = VocabItem(token=token, language=language, definition=canonical_definition)
            session.add(item)
            await session.flush()
        review = (
            await session.execute(
                select(Review).where(Review.user_id == user.id, Review.vocab_item_id == item.id)
            )
        ).scalar_one_or_none()
        if review is None:
            session.add(Review(user_id=user.id, vocab_item_id=item.id, due_at=now))
            created += 1
    await session.commit()
    return created


async def provision_user(session: AsyncSession, identity: GoogleIdentity) -> User:
    """Find-or-create the User for a *verified* Google identity, then ensure their
    starter deck (seed on first login / no reviews yet, else heal empty definitions).

    The single provisioning path shared by the web `/auth/callback` and the extension
    `/auth/extension` endpoint — keyed on the verified `sub`, so both logins trust the
    same basis. The caller owns verification (this never decodes a token) and any
    session/token issuance. Returns the persisted User.
    """
    # Keyed on the verified Google `sub` (stable, never reused) — never email. NOTE:
    # `sub` is shared across our web + extension OAuth clients ONLY if both live in the
    # same Google Cloud project; a separate project issues a different sub for the same
    # person and would split their account. Keep both clients in one project.
    user = (
        await session.execute(select(User).where(User.google_id == identity.sub))
    ).scalar_one_or_none()

    is_new = False
    if user is not None:
        user.email = identity.email
        user.name = identity.name
        user.avatar_url = identity.picture
    else:
        user = User(
            email=identity.email,
            google_id=identity.sub,
            name=identity.name,
            avatar_url=identity.picture,
        )
        session.add(user)
        is_new = True

    await session.commit()
    await session.refresh(user)

    existing_review_id = (
        await session.execute(select(Review.id).where(Review.user_id == user.id).limit(1))
    ).scalar_one_or_none()
    if is_new or existing_review_id is None:
        await _seed_starter_vocab(session, user)
    else:
        await _heal_starter_vocab_definitions(session)
    return user
