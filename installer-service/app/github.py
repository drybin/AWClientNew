import asyncio
import io
import zipfile
from datetime import datetime, timezone

import httpx

from app.config import settings

_BASE = "https://api.github.com"
_WORKFLOW_FILE = "build-installer.yml"
_ARTIFACT_NAME = "otguru-agent-installer"
_DISPATCH_TIMEOUT_SEC = 180
_POLL_INTERVAL_SEC = 15


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


async def dispatch_workflow(inputs: dict) -> datetime:
    """Trigger workflow_dispatch and return the time just before dispatch."""
    dispatch_time = datetime.now(timezone.utc)
    url = (
        f"{_BASE}/repos/{settings.github_owner}/{settings.github_repo}"
        f"/actions/workflows/{_WORKFLOW_FILE}/dispatches"
    )
    async with httpx.AsyncClient(headers=_headers(), timeout=30) as client:
        resp = await client.post(url, json={"ref": "main", "inputs": inputs})
        resp.raise_for_status()
    return dispatch_time


async def find_run_id(dispatch_time: datetime) -> int:
    """Poll for the run created after dispatch_time. Raises TimeoutError."""
    url = (
        f"{_BASE}/repos/{settings.github_owner}/{settings.github_repo}"
        f"/actions/workflows/{_WORKFLOW_FILE}/runs"
    )
    created_filter = dispatch_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    deadline = asyncio.get_event_loop().time() + _DISPATCH_TIMEOUT_SEC

    async with httpx.AsyncClient(headers=_headers(), timeout=30) as client:
        while asyncio.get_event_loop().time() < deadline:
            resp = await client.get(
                url,
                params={"event": "workflow_dispatch", "created": f">={created_filter}"},
            )
            resp.raise_for_status()
            runs = resp.json().get("workflow_runs", [])
            if runs:
                return runs[0]["id"]
            await asyncio.sleep(_POLL_INTERVAL_SEC)

    raise TimeoutError("Timed out waiting for GitHub Actions run to appear")


async def wait_for_run(run_id: int) -> str:
    """Poll until run completes. Returns conclusion string."""
    url = (
        f"{_BASE}/repos/{settings.github_owner}/{settings.github_repo}"
        f"/actions/runs/{run_id}"
    )
    async with httpx.AsyncClient(headers=_headers(), timeout=30) as client:
        while True:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            if data["status"] == "completed":
                return data["conclusion"]
            await asyncio.sleep(_POLL_INTERVAL_SEC)


async def download_installer(run_id: int, dest_dir: str) -> str:
    """Download artifact zip, extract agent_installer.exe, return file path."""
    import os

    artifacts_url = (
        f"{_BASE}/repos/{settings.github_owner}/{settings.github_repo}"
        f"/actions/runs/{run_id}/artifacts"
    )
    async with httpx.AsyncClient(
        headers=_headers(), timeout=120, follow_redirects=True
    ) as client:
        resp = await client.get(artifacts_url)
        resp.raise_for_status()
        artifacts = resp.json().get("artifacts", [])
        artifact = next(
            (a for a in artifacts if a["name"] == _ARTIFACT_NAME), None
        )
        if artifact is None:
            raise ValueError(
                f"Artifact '{_ARTIFACT_NAME}' not found in run {run_id}"
            )

        download_url = (
            f"{_BASE}/repos/{settings.github_owner}/{settings.github_repo}"
            f"/actions/artifacts/{artifact['id']}/zip"
        )
        resp = await client.get(download_url)
        resp.raise_for_status()
        zip_bytes = resp.content

    os.makedirs(dest_dir, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        zf.extract("agent_installer.exe", dest_dir)

    return os.path.join(dest_dir, "agent_installer.exe")
