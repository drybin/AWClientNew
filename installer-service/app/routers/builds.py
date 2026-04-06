import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud, worker
from app.database import get_db
from app.schemas import BuildRequest, BuildResponse, BuildStatusResponse

router = APIRouter(prefix="/builds", tags=["builds"])


@router.post("", status_code=202, response_model=BuildResponse)
async def create_build(body: BuildRequest, db: AsyncSession = Depends(get_db)):
    installer_id = f"inst_{uuid.uuid4().hex[:8]}"
    config = {**body.model_dump(exclude_none=True), "installer_id": installer_id}
    build = await crud.create_build(db, config)
    worker.start_build(build.id, config)
    return build


@router.get("/{build_id}", response_model=BuildStatusResponse)
async def get_build(build_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    build = await crud.get_build(db, build_id)
    if build is None:
        raise HTTPException(status_code=404, detail="Build not found")
    return build


@router.get("/{build_id}/download")
async def download_build(build_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    build = await crud.get_build(db, build_id)
    if build is None:
        raise HTTPException(status_code=404, detail="Build not found")
    if build.status != "success":
        raise HTTPException(
            status_code=409,
            detail=f"Build is not ready (status={build.status})",
        )
    path = Path(build.artifact_path)
    if not path.exists():
        raise HTTPException(status_code=410, detail="Artifact file not found on disk")
    return FileResponse(
        path=str(path),
        filename="agent_installer.exe",
        media_type="application/octet-stream",
    )
