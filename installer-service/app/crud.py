import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Build


async def create_build(db: AsyncSession, config: dict) -> Build:
    now = datetime.now(timezone.utc)
    build = Build(
        id=uuid.uuid4(),
        status="pending",
        config=config,
        expires_at=now + timedelta(hours=settings.installer_ttl_hours),
    )
    db.add(build)
    await db.commit()
    await db.refresh(build)
    return build


async def get_build(db: AsyncSession, build_id: uuid.UUID) -> Build | None:
    result = await db.execute(select(Build).where(Build.id == build_id))
    return result.scalar_one_or_none()


async def update_build(db: AsyncSession, build_id: uuid.UUID, **fields) -> None:
    fields["updated_at"] = datetime.now(timezone.utc)
    await db.execute(update(Build).where(Build.id == build_id).values(**fields))
    await db.commit()


async def get_expired_builds(db: AsyncSession) -> list[Build]:
    now = datetime.now(timezone.utc)
    result = await db.execute(select(Build).where(Build.expires_at <= now))
    return list(result.scalars().all())
