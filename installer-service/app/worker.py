import asyncio
import logging
import os
import uuid

from app import crud, github
from app.config import settings
from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def run_build(build_id: uuid.UUID, config: dict) -> None:
    """Full state machine for one build. Runs as a background task."""
    async with AsyncSessionLocal() as db:
        try:
            inputs = {**{k: str(v) for k, v in config.items()}, "build_id": str(build_id)}

            dispatch_time = await github.dispatch_workflow(inputs)
            await crud.update_build(db, build_id, status="queued")

            run_id = await github.find_run_id(dispatch_time)
            await crud.update_build(db, build_id, status="running", gh_run_id=run_id)

            conclusion = await github.wait_for_run(run_id)
            if conclusion != "success":
                raise RuntimeError(
                    f"GitHub Actions run {run_id} finished with conclusion={conclusion!r}"
                )

            dest_dir = os.path.join(settings.installer_dir, str(build_id))
            artifact_path = await github.download_installer(run_id, dest_dir)

            await crud.update_build(
                db,
                build_id,
                status="success",
                artifact_path=artifact_path,
            )
            logger.info("Build %s succeeded: %s", build_id, artifact_path)

        except Exception as exc:
            logger.exception("Build %s failed", build_id)
            try:
                async with AsyncSessionLocal() as db2:
                    await crud.update_build(
                        db2, build_id, status="failed", error=str(exc)
                    )
            except Exception:
                logger.exception("Could not persist failure for build %s", build_id)


def start_build(build_id: uuid.UUID, config: dict) -> None:
    """Schedule the build state machine as a fire-and-forget asyncio task."""
    asyncio.create_task(run_build(build_id, config))
