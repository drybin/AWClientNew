"""Allow only one running aw-qt process (Windows named mutex, Unix flock).

Set environment variable AW_ALLOW_MULTIPLE_INSTANCES=1 to bypass (development only).
"""

from __future__ import annotations

import os
import sys
from typing import Any, Optional

ERROR_ALREADY_EXISTS = 183
MB_OK = 0x00000000
MB_ICONINFORMATION = 0x00000040

_mutex_handle: Optional[int] = None
_lock_fp: Optional[Any] = None


def _notify_already_running() -> None:
    msg = (
        "CtrlDesk is already running.\n"
        "Check the system tray (notification area, ^ hidden icons) for the icon."
    )
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, msg, "CtrlDesk", MB_OK | MB_ICONINFORMATION)
    else:
        print(msg, file=sys.stderr)


def _win32_acquire() -> bool:
    global _mutex_handle
    import ctypes

    kernel32 = ctypes.windll.kernel32
    kernel32.SetLastError(0)
    # Local\ = per session; avoids needing Global\ admin rights
    name = "Local\\ActivityWatchSingleInstance"
    handle = kernel32.CreateMutexW(None, False, name)
    if not handle:
        return True
    if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        return False
    _mutex_handle = handle
    return True


def _unix_acquire_lockfile() -> bool:
    global _lock_fp
    import fcntl
    from pathlib import Path

    from aw_core.dirs import get_data_dir

    try:
        lock_path = Path(get_data_dir(None)) / ".aw-qt-single-instance.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        _lock_fp = open(lock_path, "a+")
        fcntl.flock(_lock_fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        try:
            if _lock_fp is not None:
                _lock_fp.close()
        except OSError:
            pass
        _lock_fp = None
        return False
    except OSError:
        # Fail open if data dir or lock is unusable
        return True
    return True


def ensure_single_instance() -> bool:
    """Return True if this process should continue; False if another instance is active."""
    if os.environ.get("AW_ALLOW_MULTIPLE_INSTANCES", "").strip() == "1":
        return True
    if sys.platform == "win32":
        ok = _win32_acquire()
    else:
        ok = _unix_acquire_lockfile()
    if not ok:
        _notify_already_running()
    return ok
