"""Where uploaded files live.

The local disk (config.STORAGE_DIR) is always the WORKING copy: Sarvam, Cognee and the PDF viewer all need a real file path.
When Supabase Storage is configured (SUPABASE_URL + SUPABASE_SERVICE_KEY) every file is also written through to a private bucket, and a file that is
missing locally (after a restart or redeploy of a server with a temporary disk) is downloaded again on demand. With nothing configured it is plain local disk.

Keys in the bucket are the file's path relative to STORAGE_DIR, made safe: `KYB-20814/ab12cd34ef56_GST.pdf`.
Remote failures never break a request: a failed write-through is logged (the file is still on the local disk); a failed restore raises FileNotFoundError.
"""
import logging
import mimetypes
import re
from pathlib import Path
from urllib.parse import quote

import httpx

from app import config

log = logging.getLogger("karyakarta.storage")
TIMEOUT = httpx.Timeout(60.0, connect=10.0)
_UNSAFE = re.compile(r"[^A-Za-z0-9._\-/]")


def configured() -> bool:
    return bool(config.SUPABASE_URL and config.SUPABASE_SERVICE_KEY)


def key_for(path: Path | str) -> str:
    """The bucket key of a file under STORAGE_DIR."""
    p = Path(path).resolve()
    rel = p.relative_to(Path(config.STORAGE_DIR).resolve())
    return _UNSAFE.sub("_", rel.as_posix())


def _headers(extra: dict | None = None) -> dict:
    return {"Authorization": f"Bearer {config.SUPABASE_SERVICE_KEY}", "apikey": config.SUPABASE_SERVICE_KEY, **(extra or {})}


def _object_url(key: str) -> str:
    return f"{config.SUPABASE_URL}/storage/v1/object/{config.SUPABASE_BUCKET}/{quote(key, safe='/')}"


def save_remote(path: Path | str) -> bool:
    """Write the local file through to the bucket. Returns True when it is stored there (or no bucket is configured)."""
    if not configured():
        return True
    p = Path(path)
    try:
        ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        r = httpx.post(_object_url(key_for(p)), content=p.read_bytes(), timeout=TIMEOUT, headers=_headers({"Content-Type": ctype, "x-upsert": "true"}))
        r.raise_for_status()
        return True
    except Exception as e:  # noqa: BLE001 - the local copy still exists; do not fail the upload
        log.warning("could not store %s in Supabase Storage: %s", p.name, e)
        return False


def ensure_local(path: Path | str) -> Path:
    """The local path of a stored file, downloading it from the bucket first if the local copy is gone."""
    p = Path(path)
    if p.exists():
        return p
    if not configured():
        raise FileNotFoundError(f"{p.name} is not on this server's disk and no file storage is configured")
    try:
        r = httpx.get(_object_url(key_for(p)), timeout=TIMEOUT, headers=_headers())
        r.raise_for_status()
    except Exception as e:  # noqa: BLE001
        raise FileNotFoundError(f"{p.name} could not be restored from file storage: {e}") from e
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(r.content)
    return p


def delete(path: Path | str) -> None:
    """Remove a file from the local disk and the bucket (best effort on the bucket)."""
    p = Path(path)
    root = Path(config.STORAGE_DIR).resolve()
    if root in p.resolve().parents and p.exists():
        p.unlink()
    if configured():
        try:
            r = httpx.request("DELETE", f"{config.SUPABASE_URL}/storage/v1/object/{config.SUPABASE_BUCKET}", timeout=TIMEOUT,
                              headers=_headers({"Content-Type": "application/json"}), json={"prefixes": [key_for(p)]})
            r.raise_for_status()
        except Exception as e:  # noqa: BLE001
            log.warning("could not delete %s from Supabase Storage: %s", p.name, e)


def delete_prefix(folder: Path | str) -> None:
    """Remove every file under a folder of STORAGE_DIR (a case's uploads), locally and in the bucket."""
    f = Path(folder)
    root = Path(config.STORAGE_DIR).resolve()
    if root not in f.resolve().parents:
        return
    keys = []
    if configured():
        prefix = key_for(f)
        try:
            r = httpx.post(f"{config.SUPABASE_URL}/storage/v1/object/list/{config.SUPABASE_BUCKET}", timeout=TIMEOUT, headers=_headers(), json={"prefix": prefix, "limit": 1000})
            r.raise_for_status()
            keys = [f"{prefix}/{o['name']}" for o in r.json() if o.get("name") and o.get("id")]
            for sub in [o["name"] for o in r.json() if o.get("name") and not o.get("id")]:     # one level of sub-folders (cpv/)
                r2 = httpx.post(f"{config.SUPABASE_URL}/storage/v1/object/list/{config.SUPABASE_BUCKET}", timeout=TIMEOUT, headers=_headers(),
                                json={"prefix": f"{prefix}/{sub}", "limit": 1000})
                r2.raise_for_status()
                keys += [f"{prefix}/{sub}/{o['name']}" for o in r2.json() if o.get("name") and o.get("id")]
        except Exception as e:  # noqa: BLE001
            log.warning("could not list %s in Supabase Storage: %s", prefix, e)
        if keys:
            try:
                httpx.request("DELETE", f"{config.SUPABASE_URL}/storage/v1/object/{config.SUPABASE_BUCKET}", timeout=TIMEOUT,
                              headers=_headers({"Content-Type": "application/json"}), json={"prefixes": keys}).raise_for_status()
            except Exception as e:  # noqa: BLE001
                log.warning("could not delete %s from Supabase Storage: %s", prefix, e)
    if f.exists():
        import shutil
        shutil.rmtree(f, ignore_errors=True)
