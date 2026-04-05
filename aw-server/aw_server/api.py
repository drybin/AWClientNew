import functools
import json
import logging
from datetime import datetime
from pathlib import Path
from socket import gethostname
from typing import (
    Any,
    Dict,
    List,
    Optional,
)
from uuid import uuid4

import requests
import requests as req

import iso8601
from aw_core.dirs import get_data_dir
from aw_core.log import get_log_file_path
from aw_core.models import Event
from aw_query import query2
from aw_transform import heartbeat_merge

from .__about__ import __version__
from .exceptions import NotFound
from .settings import CENTRAL_DEFAULTS, Settings

logger = logging.getLogger(__name__)

# Base58 invitation token in this file (single line). Read on first startup; removed after success.
PRELOAD_FILENAME = "preload.txt"


def _unlink_preload_safe(path: Path) -> None:
    try:
        path.unlink()
    except OSError as e:
        logger.warning("Could not remove invitation token file: %s", e)


def get_device_id() -> str:
    path = Path(get_data_dir("aw-server")) / "device_id"
    if path.exists():
        with open(path) as f:
            return f.read()
    else:
        uuid = str(uuid4())
        with open(path, "w") as f:
            f.write(uuid)
        return uuid


def check_bucket_exists(f):
    @functools.wraps(f)
    def g(self, bucket_id, *args, **kwargs):
        if bucket_id not in self.db.buckets():
            raise NotFound("NoSuchBucket", f"There's no bucket named {bucket_id}")
        return f(self, bucket_id, *args, **kwargs)

    return g


class ServerAPI:
    def __init__(self, db, testing) -> None:
        self.db = db
        self.settings = Settings(testing)
        self.testing = testing
        self.last_event = {}  # type: dict
        self._central_banner_logged = False

    def forward_heartbeat_to_central(self, endpoint, method, data):

        gfps_enabled = False
        if not self.settings.get("gfpsEnabled") is None:
            gfps_enabled = self.settings["gfpsEnabled"]
        gfps_ip = ""
        if not self.settings.get("gfpsServerIP") is None:
            gfps_ip = self.settings["gfpsServerIP"]
        gfps_port = ""
        if not self.settings.get("gfpsServerPort") is None:
            gfps_port = self.settings["gfpsServerPort"]

        if not gfps_enabled:
            return False

        url = f"http://{gfps_ip}:{gfps_port}/api/0/" + endpoint
        logger.debug("Central heartbeat %s %s", method, url)
        headers = {"Content-Type": "application/json"}
        if method == "POST":
            try:
                return req.post(url, data=bytes(json.dumps(data), "utf8"), headers=headers)
            except Exception as e:
                return {"status": "error", "message": str(e)}
        elif method == "PUT":
            try:
                return req.put(url, data=bytes(json.dumps(data), "utf8"), headers=headers)
            except Exception as e:
                return {"status": "error", "message": str(e)}
        elif method == "DELETE":
            try:
                return req.delete(url, data=bytes(json.dumps(data), "utf8"), headers=headers)
            except Exception as e:
                return {"status": "error", "message": str(e)}
        elif method == "GET":
            try:
                return req.get(url)
            except Exception as e:
                return {"status": "error", "message": str(e)}, 200
        raise Exception("Invalid method")

    def get_info(self) -> Dict[str, Any]:
        """Get server info"""
        payload = {
            "hostname": gethostname(),
            "version": __version__,
            "testing": self.testing,
            "device_id": get_device_id(),
        }
        return payload

    def get_buckets(self) -> Dict[str, Dict]:
        """Get dict {bucket_name: Bucket} of all buckets"""
        logger.debug("Received get request for buckets")
        buckets = self.db.buckets()
        for b in buckets:
            # TODO: Move this code to aw-core?
            last_events = self.db[b].get(limit=1)
            if len(last_events) > 0:
                last_event = last_events[0]
                last_updated = last_event.timestamp + last_event.duration
                buckets[b]["last_updated"] = last_updated.isoformat()
        return buckets

    @check_bucket_exists
    def get_bucket_metadata(self, bucket_id: str) -> Dict[str, Any]:
        """Get metadata about bucket."""
        bucket = self.db[bucket_id]
        return bucket.metadata()

    @check_bucket_exists
    def export_bucket(self, bucket_id: str) -> Dict[str, Any]:
        """Export a bucket to a dataformat consistent across versions, including all events in it."""
        bucket = self.get_bucket_metadata(bucket_id)
        bucket["events"] = self.get_events(bucket_id, limit=-1)
        # Scrub event IDs
        for event in bucket["events"]:
            del event["id"]
        return bucket

    def export_all(self) -> Dict[str, Any]:
        """Exports all buckets and their events to a format consistent across versions"""
        buckets = self.get_buckets()
        exported_buckets = {}
        for bid in buckets.keys():
            exported_buckets[bid] = self.export_bucket(bid)
        return exported_buckets

    def import_bucket(self, bucket_data: Any):
        bucket_id = bucket_data["id"]
        logger.info(f"Importing bucket {bucket_id}")

        # TODO: Check that bucket doesn't already exist
        self.db.create_bucket(
            bucket_id,
            type=bucket_data["type"],
            client=bucket_data["client"],
            hostname=bucket_data["hostname"],
            created=(
                bucket_data["created"]
                if isinstance(bucket_data["created"], datetime)
                else iso8601.parse_date(bucket_data["created"])
            ),
        )

        # scrub IDs from events
        # (otherwise causes weird bugs with no events seemingly imported when importing events exported from aw-server-rust, which contains IDs)
        for event in bucket_data["events"]:
            if "id" in event:
                del event["id"]

        self.create_events(
            bucket_id,
            [Event(**e) if isinstance(e, dict) else e for e in bucket_data["events"]],
        )

    def import_all(self, buckets: Dict[str, Any]):
        for bid, bucket in buckets.items():
            self.import_bucket(bucket)

    def create_bucket(
        self,
        bucket_id: str,
        event_type: str,
        client: str,
        hostname: str,
        created: Optional[datetime] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Create a bucket.

        If hostname is "!local", the hostname and device_id will be set from the server info.
        This is useful for watchers which are known/assumed to run locally but might not know their hostname (like aw-watcher-web).

        Returns True if successful, otherwise false if a bucket with the given ID already existed.
        """
        if created is None:
            created = datetime.now()
        if bucket_id in self.db.buckets():
            return False
        if hostname == "!local":
            info = self.get_info()
            if data is None:
                data = {}
            hostname = info["hostname"]
            data["device_id"] = info["device_id"]
        self.db.create_bucket(
            bucket_id,
            type=event_type,
            client=client,
            hostname=hostname,
            created=created,
            data=data,
        )
        return True

    @check_bucket_exists
    def update_bucket(
        self,
        bucket_id: str,
        event_type: Optional[str] = None,
        client: Optional[str] = None,
        hostname: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update bucket metadata"""
        self.db.update_bucket(
            bucket_id,
            type=event_type,
            client=client,
            hostname=hostname,
            data=data,
        )
        return None

    @check_bucket_exists
    def delete_bucket(self, bucket_id: str) -> None:
        """Delete a bucket"""
        self.db.delete_bucket(bucket_id)
        logger.debug(f"Deleted bucket '{bucket_id}'")
        return None

    @check_bucket_exists
    def get_event(
        self,
        bucket_id: str,
        event_id: int,
    ) -> Optional[Event]:
        """Get a single event from a bucket"""
        logger.debug(
            f"Received get request for event {event_id} in bucket '{bucket_id}'"
        )
        event = self.db[bucket_id].get_by_id(event_id)
        return event.to_json_dict() if event else None

    @check_bucket_exists
    def get_events(
        self,
        bucket_id: str,
        limit: int = -1,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> List[Event]:
        """Get events from a bucket"""
        logger.debug(f"Received get request for events in bucket '{bucket_id}'")
        if limit is None:  # Let limit = None also mean "no limit"
            limit = -1
        events = [
            event.to_json_dict() for event in self.db[bucket_id].get(limit, start, end)
        ]
        return events

    @check_bucket_exists
    def create_events(self, bucket_id: str, events: List[Event]) -> Optional[Event]:
        """Create events for a bucket. Can handle both single events and multiple ones.

        Returns the inserted event when a single event was inserted, otherwise None."""
        return self.db[bucket_id].insert(events)

    @check_bucket_exists
    def get_eventcount(
        self,
        bucket_id: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> int:
        """Get eventcount from a bucket"""
        logger.debug(f"Received get request for eventcount in bucket '{bucket_id}'")
        return self.db[bucket_id].get_eventcount(start, end)

    @check_bucket_exists
    def delete_event(self, bucket_id: str, event_id) -> bool:
        """Delete a single event from a bucket"""
        return self.db[bucket_id].delete(event_id)

    @check_bucket_exists
    def heartbeat(self, bucket_id: str, heartbeat: Event, pulsetime: float) -> Event:
        logger.debug(
            "Received heartbeat in bucket '{}'\n\ttimestamp: {}, duration: {}, pulsetime: {}\n\tdata: {}".format(
                bucket_id,
                heartbeat.timestamp,
                heartbeat.duration,
                pulsetime,
                heartbeat.data,
            )
        )
        gfps_response = self.forward_heartbeat_to_central(f"buckets/{bucket_id}/heartbeat?pulsetime={pulsetime}", "POST", data={**heartbeat.to_json_dict(), "uuid": get_device_id()})
        if type(gfps_response) == req.Response:
            try:
                resp_data = gfps_response.json()
            except Exception:
                resp_data = {}
            if resp_data.get("message", "").startswith("There's no bucket"):
                gfps_response = self.forward_heartbeat_to_central("buckets/" + bucket_id, "POST", {
                               "client": self.db[bucket_id].metadata()["client"],
                               "hostname": self.db[bucket_id].metadata()["hostname"],
                               "type": self.db[bucket_id].metadata()["type"],
                               "uuid": get_device_id()
                           })

        last_event = None
        if bucket_id not in self.last_event:
            last_events = self.db[bucket_id].get(limit=1)
            if len(last_events) > 0:
                last_event = last_events[0]
        else:
            last_event = self.last_event[bucket_id]
        if last_event:
            if last_event.data == heartbeat.data:
                merged = heartbeat_merge(last_event, heartbeat, pulsetime)
                if merged is not None:
                    # Heartbeat was merged into last_event
                    logger.debug(
                        "Received valid heartbeat, merging. (bucket: {})".format(
                            bucket_id
                        )
                    )
                    self.last_event[bucket_id] = merged
                    self.db[bucket_id].replace_last(merged)
                    return merged
                else:
                    logger.debug(
                        "Heartbeat after pulse window, new event (bucket: %s)", bucket_id
                    )
            else:
                logger.debug(
                    "Heartbeat with differing data, new event (bucket: %s)", bucket_id
                )
        else:
            logger.debug(
                "Heartbeat on previously empty bucket, new event (bucket: %s)", bucket_id
            )
        self.db[bucket_id].insert(heartbeat)
        self.last_event[bucket_id] = heartbeat
        return heartbeat

    def query2(self, name, query, timeperiods, cache):
        result = []
        for timeperiod in timeperiods:
            period = timeperiod.split("/")[
                :2
            ]  # iso8601 timeperiods are separated by a slash
            starttime = iso8601.parse_date(period[0])
            endtime = iso8601.parse_date(period[1])
            query = "".join(query)
            result.append(query2.query(name, query, starttime, endtime, self.db))
        return result

    # TODO: Right now the log format on disk has to be JSON, this is hard to read by humans...
    def get_log(self):
        """Get the server log in json format"""
        payload = []
        with open(get_log_file_path()) as log_file:
            for line in log_file.readlines()[::-1]:
                payload.append(json.loads(line))
        return payload, 200

    def get_setting(self, key):
        """Get a setting"""
        return self.settings.get(key, None)

    def set_setting(self, key, value):
        """Set a setting"""
        self.settings[key] = value
        return value

    def _central_base_url(self) -> Optional[str]:
        """HTTP base URL for central GFP/TIM (invitation claim, version sync).

        `gfpsEnabled` only gates heartbeat forwarding via `forward_heartbeat_to_central`.
        Missing host/port fall back to CENTRAL_DEFAULTS in settings.py.
        """
        raw_ip = self.settings.get("gfpsServerIP")
        raw_port = self.settings.get("gfpsServerPort")
        if raw_ip is None or (isinstance(raw_ip, str) and not raw_ip.strip()):
            ip = str(CENTRAL_DEFAULTS["gfpsServerIP"])
        else:
            ip = str(raw_ip).strip()
        if raw_port is None or raw_port == "":
            port = int(CENTRAL_DEFAULTS["gfpsServerPort"])
        else:
            try:
                port = int(raw_port)
            except (TypeError, ValueError):
                logger.warning(
                    "Invalid gfpsServerPort %r; using %s",
                    raw_port,
                    CENTRAL_DEFAULTS["gfpsServerPort"],
                )
                port = int(CENTRAL_DEFAULTS["gfpsServerPort"])
        try:
            return f"http://{ip}:{port}"
        except Exception:
            logger.warning("Could not build central base URL (ip=%r port=%r)", ip, port)
            return None

    def run_central_sync(self) -> None:
        """Sync with central server: preload invitation claim + client_version update.
        Invoked at startup and on a fixed background interval."""
        base = self._central_base_url()
        if not base:
            logger.warning("Central sync skipped: no base URL (host/port)")
            return
        if not self._central_banner_logged:
            self._central_banner_logged = True
            p = self._invitation_token_path()
            preload_len = 0
            if p.is_file():
                try:
                    preload_len = len(p.read_text(encoding="utf-8").strip())
                except OSError as e:
                    logger.warning("Could not read preload length from %s: %s", p, e)
            logger.info(
                "Central sync: base=%s preload=%s has_token=%s token_len=%s gfps_enabled=%s host=%s port=%s",
                base,
                p,
                p.is_file(),
                preload_len,
                self.settings.get("gfpsEnabled"),
                self.settings.get("gfpsServerIP"),
                self.settings.get("gfpsServerPort"),
            )
        self._try_preload_invitation_claim(base)
        self._sync_client_version_to_central(base)

    def _invitation_token_path(self) -> Path:
        return Path(get_data_dir("aw-server")) / PRELOAD_FILENAME

    def _post_invitation_claim(self, base: str, token: str) -> dict:
        """POST /api/0/gfps/invitations/claim on central (body: token + uuid)."""
        device_uuid = get_device_id()
        url = f"{base}/api/0/gfps/invitations/claim"
        payload: Dict[str, Any] = {"token": token, "uuid": device_uuid}
        logger.debug(
            "Invitation claim POST %s token_len=%d uuid=%s…",
            url,
            len(token),
            device_uuid[:8],
        )
        r = requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=120,
        )
        snippet = (r.text or "")[:500]
        if r.status_code != 200:
            logger.warning(
                "Invitation claim: HTTP %s len=%s body=%r",
                r.status_code,
                len(r.content or b""),
                snippet,
            )
            if not r.content:
                return {}
            try:
                body = r.json()
            except ValueError:
                return {}
            if isinstance(body, dict) and body.get("status") == "error":
                logger.warning(
                    "Invitation claim: %s",
                    body.get("message") or body.get("error") or body,
                )
            return body if isinstance(body, dict) else {}
        if not r.content:
            logger.warning("Invitation claim: empty response body (HTTP %s)", r.status_code)
            return {}
        try:
            body = r.json()
        except ValueError:
            logger.warning(
                "Invitation claim: response not JSON (HTTP %s) body=%r",
                r.status_code,
                snippet,
            )
            return {}
        if not isinstance(body, dict):
            logger.warning("Invitation claim: unexpected response type %s", type(body))
            return {}
        if body.get("status") == "error":
            logger.warning(
                "Invitation claim: %s",
                body.get("message") or body.get("error") or body,
            )
        return body

    def _handle_preload_claim_response(self, path: Path, body: dict) -> None:
        """Remove preload.txt after any definitive server response (success or invalid token)."""
        if body.get("status") == "success":
            logger.info("Preload invitation: ok; removed %s", path.name)
            _unlink_preload_safe(path)
            return
        err_code = body.get("error")
        if body.get("status") == "error":
            if err_code == "uuid_already_registered":
                logger.info(
                    "Preload invitation: device already registered; removed stale %s", path.name
                )
            # Other errors: already logged in _post_invitation_claim
            _unlink_preload_safe(path)
            return
        logger.warning("Preload invitation: unexpected response: %s", body)
        _unlink_preload_safe(path)

    def _try_preload_invitation_claim(self, base: str) -> None:
        path = self._invitation_token_path()
        if not path.is_file():
            logger.debug("Preload invitation: no file at %s", path)
            return
        try:
            token = path.read_text(encoding="utf-8").strip()
        except OSError as e:
            logger.warning("Could not read %s: %s", path, e)
            return
        if not token:
            logger.warning("Preload invitation: empty file %s", path)
            return
        logger.debug(
            "Preload invitation: claiming (path=%s token_len=%d base=%s)",
            path,
            len(token),
            base,
        )
        try:
            body = self._post_invitation_claim(base, token)
        except Exception as e:
            logger.warning("Invitation claim failed (network): %s", e)
            return
        self._handle_preload_claim_response(path, body)

    def claim_invitation_token(self, token: str) -> dict:
        """Proxy invitation claim (web UI). Body on wire: token + uuid; profile fields via PUT /api/0/user."""
        token = (token or "").strip()
        if not token:
            return {"status": "error", "error": "empty_token", "message": "Token is empty"}
        base = self._central_base_url()
        if not base:
            return {
                "status": "error",
                "error": "gfps_unconfigured",
                "message": "Central server address is not configured",
            }
        try:
            body = self._post_invitation_claim(base, token)
        except Exception as e:
            logger.warning("Invitation claim failed (network): %s", e)
            return {"status": "error", "error": "network", "message": str(e)}
        if body.get("status") == "success":
            logger.info("Invitation claim: success")
            path = self._invitation_token_path()
            if path.is_file():
                try:
                    if path.read_text(encoding="utf-8").strip() == token:
                        _unlink_preload_safe(path)
                except OSError:
                    pass
        return body

    def _client_version_string(self) -> str:
        v = __version__
        return v[1:] if v.startswith("v") else v

    def _sync_client_version_to_central(self, base: str) -> None:
        device_uuid = get_device_id()
        get_url = f"{base}/api/0/user/{device_uuid}"
        try:
            r = requests.get(get_url, timeout=30)
            if r.status_code == 404:
                return
            body = r.json() if r.content else {}
        except Exception as e:
            logger.debug("Client version sync: user GET skipped: %s", e)
            return
        user = body.get("user") if isinstance(body, dict) else None
        if not user:
            return
        remote_ver = user.get("client_version")
        local_ver = self._client_version_string()
        if remote_ver == local_ver:
            return
        put_url = f"{base}/api/0/user"
        put_body = {"uuid": device_uuid, "client_version": local_ver}
        logger.info(
            "Client version sync: %s -> %s",
            remote_ver,
            local_ver,
        )
        try:
            pr = requests.put(put_url, json=put_body, timeout=30)
            pr_body = pr.json() if pr.content else {}
            if pr_body.get("status") != "ok" and pr.status_code != 200:
                logger.warning("Client version sync: unexpected PUT response: %s", pr_body)
        except Exception as e:
            logger.warning("Client version sync failed: %s", e)
