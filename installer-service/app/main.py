import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import cleanup
from app.routers import builds

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(cleanup.cleanup_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Installer Service", lifespan=lifespan)
app.include_router(builds.router)
