import hashlib
import math
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Set
from uuid import uuid4

import aiofiles
from fastapi import HTTPException

from .config import DEFAULT_CHUNK_SIZE, FILE_STORAGE_DIR, MAX_CHUNK_SIZE, UPLOAD_TMP_DIR
from .db import db
from .rate_limiter import rate_limiter


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sanitize_filename(name: str) -> str:
    # Prevent path traversal while keeping relative folder structure for UI.
    if not name:
        return f"unnamed-{uuid4().hex[:8]}"

    normalized = name.replace("\\", "/").strip()
    parts = []
    for part in normalized.split("/"):
        part = part.strip()
        if not part or part in (".", ".."):
            continue
        parts.append(part.replace(":", "_"))

    cleaned = "/".join(parts)
    return cleaned or f"unnamed-{uuid4().hex[:8]}"


def get_upload_dir(upload_id: str) -> Path:
    directory = UPLOAD_TMP_DIR / upload_id
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def chunk_path(upload_id: str, chunk_index: int) -> Path:
    return get_upload_dir(upload_id) / f"{chunk_index}.part"


def _ensure_quota(user: Dict, incoming_file_size: int):
    used_files = db.sum_user_file_size(user["user_id"])
    pending = db.sum_user_pending_upload_size(user["user_id"])
    total_will_be = used_files + pending + incoming_file_size
    if total_will_be > int(user["storage_quota_bytes"]):
        raise HTTPException(status_code=403, detail="storage quota exceeded")


def init_upload(user: Dict, file_name: str, file_size: int, file_hash: str, chunk_size: int) -> Dict:
    if chunk_size > MAX_CHUNK_SIZE:
        raise HTTPException(status_code=400, detail=f"chunk_size exceeds limit {MAX_CHUNK_SIZE}")

    chunk_size = chunk_size or DEFAULT_CHUNK_SIZE
    total_chunks = math.ceil(file_size / chunk_size)

    existing_file = db.get_file_by_hash(user["user_id"], file_hash)
    if existing_file:
        db.insert_upload_history(
            {
                "record_id": uuid4().hex,
                "user_id": user["user_id"],
                "file_name": sanitize_filename(file_name),
                "file_size": file_size,
                "file_hash": file_hash,
                "status": "instant",
                "message": "file already exists, instant upload",
                "created_at": utc_now(),
            }
        )
        return {
            "file_exists": True,
            "file_id": existing_file["file_id"],
            "uploaded_chunks": list(range(total_chunks)),
            "total_chunks": total_chunks,
            "chunk_size": chunk_size,
        }

    existing_task = db.get_upload_task_by_hash(user["user_id"], file_hash)
    if existing_task:
        return {
            "upload_id": existing_task["upload_id"],
            "file_exists": False,
            "uploaded_chunks": existing_task["uploaded_chunks"],
            "total_chunks": existing_task["total_chunks"],
            "chunk_size": existing_task["chunk_size"],
        }

    _ensure_quota(user, file_size)

    upload_id = uuid4().hex
    now = utc_now()
    task = {
        "upload_id": upload_id,
        "user_id": user["user_id"],
        "file_name": sanitize_filename(file_name),
        "file_size": file_size,
        "file_hash": file_hash,
        "chunk_size": chunk_size,
        "total_chunks": total_chunks,
        "uploaded_chunks": [],
        "status": "uploading",
        "created_at": now,
        "updated_at": now,
    }
    db.upsert_upload_task(task)
    get_upload_dir(upload_id)

    return {
        "upload_id": upload_id,
        "file_exists": False,
        "uploaded_chunks": [],
        "total_chunks": total_chunks,
        "chunk_size": chunk_size,
    }


def get_task_or_404(user: Dict, upload_id: str) -> Dict:
    task = db.get_upload_task(upload_id)
    if not task or task["user_id"] != user["user_id"]:
        raise HTTPException(status_code=404, detail="upload task not found")
    return task


async def save_chunk(user: Dict, upload_id: str, chunk_index: int, chunk_data):
    task = get_task_or_404(user, upload_id)
    if chunk_index < 0 or chunk_index >= task["total_chunks"]:
        raise HTTPException(status_code=400, detail="invalid chunk index")

    path = chunk_path(upload_id, chunk_index)
    async with aiofiles.open(path, "wb") as out:
        while True:
            data = await chunk_data.read(1024 * 1024)
            if not data:
                break
            await rate_limiter.consume(user["user_id"], len(data), int(user["upload_rate_bytes_sec"]))
            await out.write(data)

    db.add_uploaded_chunk(upload_id, chunk_index, utc_now())


def status(user: Dict, upload_id: str) -> Dict:
    return get_task_or_404(user, upload_id)


def _calculate_file_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(8 * 1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def merge_chunks(user: Dict, upload_id: str) -> Dict:
    task = get_task_or_404(user, upload_id)
    upload_dir = get_upload_dir(upload_id)

    expected_indexes = set(range(task["total_chunks"]))
    uploaded_indexes = set(task["uploaded_chunks"])
    disk_indexes = {idx for idx in expected_indexes if (upload_dir / f"{idx}.part").exists()}
    if disk_indexes != uploaded_indexes:
        synced = sorted(uploaded_indexes | disk_indexes)
        status = "uploaded" if len(synced) == task["total_chunks"] else "uploading"
        db.update_uploaded_chunks(upload_id, synced, status, utc_now())
        uploaded_indexes = set(synced)

    missing = sorted(expected_indexes - uploaded_indexes)
    if missing:
        raise HTTPException(status_code=400, detail={"missing_chunks": missing[:200], "missing_count": len(missing)})

    ext = Path(task["file_name"]).suffix
    merged_name = f"{task['file_hash']}{ext}" if ext else task["file_hash"]
    final_path = FILE_STORAGE_DIR / merged_name

    with final_path.open("wb") as target:
        for idx in range(task["total_chunks"]):
            part = upload_dir / f"{idx}.part"
            if not part.exists():
                raise HTTPException(status_code=400, detail=f"chunk file missing: {idx}")
            with part.open("rb") as src:
                shutil.copyfileobj(src, target, length=8 * 1024 * 1024)

    size = final_path.stat().st_size
    if size != task["file_size"]:
        final_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="merged file size mismatch")

    actual_hash = _calculate_file_sha256(final_path)
    if actual_hash != task["file_hash"]:
        final_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="hash mismatch after merge")

    file_id = uuid4().hex
    db.insert_file(
        {
            "file_id": file_id,
            "user_id": user["user_id"],
            "file_name": task["file_name"],
            "file_path": str(final_path),
            "file_size": task["file_size"],
            "file_hash": task["file_hash"],
            "created_at": utc_now(),
        }
    )
    db.insert_upload_history(
        {
            "record_id": uuid4().hex,
            "user_id": user["user_id"],
            "file_name": task["file_name"],
            "file_size": task["file_size"],
            "file_hash": task["file_hash"],
            "status": "success",
            "message": "upload merged and verified",
            "created_at": utc_now(),
        }
    )
    db.delete_upload_task(upload_id)
    shutil.rmtree(upload_dir, ignore_errors=True)

    return {
        "file_id": file_id,
        "file_name": task["file_name"],
        "file_size": task["file_size"],
        "file_hash": task["file_hash"],
    }


def list_files(user: Dict) -> List[Dict]:
    return db.list_files(user["user_id"])


def delete_file(user: Dict, file_id: str):
    record = db.get_file_by_id(user["user_id"], file_id)
    if not record:
        raise HTTPException(status_code=404, detail="file not found")

    path = Path(record["file_path"])
    if path.exists():
        path.unlink()
    db.delete_file(user["user_id"], file_id)


def get_file(user: Dict, file_id: str) -> Dict:
    record = db.get_file_by_id(user["user_id"], file_id)
    if not record:
        raise HTTPException(status_code=404, detail="file not found")
    return record


def list_history(user: Dict, page: int, page_size: int) -> Dict:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    result = db.list_upload_history(user["user_id"], page, page_size)
    return {
        "items": result["items"],
        "total": result["total"],
        "page": page,
        "page_size": page_size,
    }
