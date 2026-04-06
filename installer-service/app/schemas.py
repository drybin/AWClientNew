import uuid
from datetime import datetime

from pydantic import BaseModel


class BuildRequest(BaseModel):
    company_id: int
    tenant_id: str
    server_url: str = ""


class BuildResponse(BaseModel):
    id: uuid.UUID
    installer_id: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class BuildStatusResponse(BaseModel):
    id: uuid.UUID
    status: str
    gh_run_id: int | None
    error: str | None
    created_at: datetime
    updated_at: datetime
    expires_at: datetime

    model_config = {"from_attributes": True}
