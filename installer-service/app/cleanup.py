import asyncio
import logging
import os
import shutil

from app import crud
from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

_INTERVAL_SEC = 3600  # run every hour


async def cleanup_loop() -> None:
    """Periodically delete expired builds from DB and disk."""
    while True:
        await asyncio.sleep(_INTERVAL_SEC)
        try:
            async with AsyncSessionLocal() as db:
                expired = await crud.get_expired_builds(db)
                for build in expired:
                    _remove_files(build.artifact_path)
                    await db.delete(build)
                if expired:
                    await db.commit()
                    logger.info("Cleaned up %d expired build(s)", len(expired))
        except Exception:
            logger.exception("Error during cleanup")


def _remove_files(artifact_path: str | None) -> None:
    if not artifact_path:
        return
    parent = os.path.dirname(artifact_path)
    try:
        if os.path.isdir(parent):
            shutil.rmtree(parent)
    except OSError:
        logger.warning("Could not remove directory %s", parent)
