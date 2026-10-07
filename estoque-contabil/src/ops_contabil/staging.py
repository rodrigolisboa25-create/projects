from __future__ import annotations

import shutil
import time
import uuid
from pathlib import Path

from .audit import append_event, sha256


def wait_until_stable(path: Path, stable_seconds: int = 10, timeout_seconds: int = 900) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_signature: tuple[int, int] | None = None
    stable_since: float | None = None
    while time.monotonic() < deadline:
        stat = path.stat()
        signature = (stat.st_size, stat.st_mtime_ns)
        if signature == last_signature:
            stable_since = stable_since or time.monotonic()
            if time.monotonic() - stable_since >= stable_seconds:
                return
        else:
            last_signature = signature
            stable_since = None
        time.sleep(1)
    raise TimeoutError(f"Arquivo não estabilizou em {timeout_seconds}s: {path}")


def stage_file(source: Path, inbox: Path, source_name: str, log_dir: Path) -> dict[str, object]:
    wait_until_stable(source)
    digest = sha256(source)
    target_dir = inbox / source_name / digest[:12]
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / source.name
    if not target.exists():
        shutil.copy2(source, target)
    staged_digest = sha256(target)
    if staged_digest != digest:
        raise IOError(f"Hash divergente após staging: {source}")
    result = {
        "source_file_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{source_name}:{digest}")),
        "path": target,
        "sha256": digest,
        "size_bytes": target.stat().st_size,
    }
    append_event(log_dir, "file_staged", source=source_name, **result)
    return result
