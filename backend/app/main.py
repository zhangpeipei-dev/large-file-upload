from pathlib import Path
import io
import zipfile

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .auth import (
    ensure_admin_user,
    get_current_user,
    get_user_quota,
    login_user,
    register_user,
    require_admin,
)
from .db import db
from .schemas import (
    FileItem,
    HealthResponse,
    HistoryListResponse,
    InitUploadRequest,
    InitUploadResponse,
    LoginRequest,
    LoginResponse,
    CompleteGroupRequest,
    CompleteGroupResponse,
    ZipFilesRequest,
    MergeRequest,
    MergeResponse,
    QuotaResponse,
    RegisterRequest,
    UploadStatusResponse,
    UserInfo,
)
from .service import (
    delete_file,
    get_file,
    get_file_by_id,
    init_upload,
    list_history,
    list_files,
    merge_chunks,
    save_chunk,
    status,
    complete_group_upload,
)

app = FastAPI(title="Large File Upload Service", version="1.1.0")


@app.on_event("startup")
def startup_event():
    ensure_admin_user()


FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse)
def health():
    return {"status": "ok"}


@app.post("/api/auth/register", response_model=UserInfo)
def api_register(payload: RegisterRequest):
    return register_user(payload.username, payload.password)


@app.post("/api/auth/login", response_model=LoginResponse)
def api_login(payload: LoginRequest):
    return login_user(payload.username, payload.password)


@app.get("/api/auth/me", response_model=UserInfo)
def api_me(user: dict = Depends(get_current_user)):
    return {
        "user_id": user["user_id"],
        "username": user["username"],
        "role": user.get("role", "user"),
        "storage_quota_bytes": user["storage_quota_bytes"],
        "upload_rate_bytes_sec": user["upload_rate_bytes_sec"],
    }


@app.get("/api/auth/quota", response_model=QuotaResponse)
def api_quota(user: dict = Depends(get_current_user)):
    return get_user_quota(user)


@app.post("/api/uploads/init", response_model=InitUploadResponse)
def api_init_upload(payload: InitUploadRequest, user: dict = Depends(get_current_user)):
    return init_upload(
        user=user,
        file_name=payload.file_name,
        file_size=payload.file_size,
        file_hash=payload.file_hash,
        chunk_size=payload.chunk_size,
        group_id=payload.group_id,
        group_name=payload.group_name,
        group_total_files=payload.group_total_files,
        group_total_size=payload.group_total_size,
    )


@app.get("/api/uploads/{upload_id}", response_model=UploadStatusResponse)
def api_upload_status(upload_id: str, user: dict = Depends(get_current_user)):
    return status(user=user, upload_id=upload_id)


@app.post("/api/uploads/chunk")
async def api_upload_chunk(
    upload_id: str = Form(...),
    chunk_index: int = Form(...),
    chunk: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    await save_chunk(
        user=user, upload_id=upload_id, chunk_index=chunk_index, chunk_data=chunk
    )
    return {"ok": True}


@app.post("/api/uploads/merge", response_model=MergeResponse)
def api_merge(payload: MergeRequest, user: dict = Depends(get_current_user)):
    return merge_chunks(user=user, upload_id=payload.upload_id)


@app.post("/api/uploads/group/complete", response_model=CompleteGroupResponse)
def api_complete_group(
    payload: CompleteGroupRequest, user: dict = Depends(get_current_user)
):
    return complete_group_upload(
        user=user,
        group_id=payload.group_id,
        group_name=payload.group_name,
        group_total_files=payload.group_total_files,
        group_total_size=payload.group_total_size,
        status=payload.status,
        message=payload.message,
    )


@app.get("/api/files", response_model=list[FileItem])
def api_list_files(user: dict = Depends(get_current_user)):
    return list_files(user=user)


@app.get("/api/files/{file_id}/download")
def api_download_file(file_id: str, user: dict = Depends(get_current_user)):
    record = get_file(user=user, file_id=file_id)
    return FileResponse(
        record["file_path"],
        filename=Path(record["file_name"]).name,
        media_type="application/octet-stream",
    )


@app.get("/api/files/zip")
def api_download_zip(path: str = Query(default=""), user: dict = Depends(get_current_user)):
    all_files = list_files(user=user)
    prefix = path.strip("/").strip()

    def in_scope(file_name: str) -> bool:
        if not prefix:
            return True
        normalized = file_name.strip("/")
        return normalized == prefix or normalized.startswith(f"{prefix}/")

    selected = [f for f in all_files if in_scope(str(f.get("file_name") or ""))]
    if not selected:
        raise HTTPException(status_code=404, detail="no files under path")

    def zip_stream():
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for item in selected:
                record = get_file_by_id(user=user, file_id=item["file_id"])
                full_path = record["file_path"]
                arc_name = record["file_name"].strip("/")
                if prefix:
                    if arc_name == prefix:
                        arc_name = Path(arc_name).name
                    elif arc_name.startswith(f"{prefix}/"):
                        arc_name = arc_name[len(prefix) + 1 :]
                zf.write(full_path, arc_name)
        buffer.seek(0)
        while True:
            chunk = buffer.read(1024 * 1024)
            if not chunk:
                break
            yield chunk

    zip_name = f"{Path(prefix).name or 'files'}.zip"
    headers = {"Content-Disposition": f'attachment; filename="{zip_name}"'}
    return StreamingResponse(zip_stream(), media_type="application/zip", headers=headers)


@app.post("/api/files/zip/selected")
def api_download_selected_zip(
    payload: ZipFilesRequest, user: dict = Depends(get_current_user)
):
    unique_ids = list(dict.fromkeys(payload.file_ids))
    if not unique_ids:
        raise HTTPException(status_code=400, detail="no file ids")

    def zip_stream():
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for file_id in unique_ids:
                record = get_file_by_id(user=user, file_id=file_id)
                full_path = record["file_path"]
                arc_name = record["file_name"].strip("/")
                zf.write(full_path, arc_name)
        buffer.seek(0)
        while True:
            chunk = buffer.read(1024 * 1024)
            if not chunk:
                break
            yield chunk

    headers = {"Content-Disposition": 'attachment; filename="selected-files.zip"'}
    return StreamingResponse(zip_stream(), media_type="application/zip", headers=headers)


@app.get("/api/public/download/{file_id}")
def api_public_download(file_id: str, token: str = Query(...)):
    from .auth import decode_token, db

    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="invalid or expired token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="invalid token payload")

    user = db.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="user not found")

    record = get_file(user=user, file_id=file_id)
    return FileResponse(
        record["file_path"],
        filename=Path(record["file_name"]).name,
        media_type="application/octet-stream",
    )


@app.delete("/api/files/{file_id}")
def api_delete_file(file_id: str, user: dict = Depends(get_current_user)):
    delete_file(user=user, file_id=file_id)
    return {"ok": True}


@app.get("/api/admin/users", response_model=list[UserInfo])
def api_admin_users(role: str = Query(None), admin: dict = Depends(require_admin)):
    users = db.list_users(role_filter=role)
    for u in users:
        u.pop("password_hash", None)
    return users


@app.post("/api/admin/users/{user_id}/approve")
def api_admin_approve(user_id: str, admin: dict = Depends(require_admin)):
    db.update_user_role(user_id, "user")
    return {"ok": True}


@app.delete("/api/admin/users/{user_id}")
def api_admin_delete_user(user_id: str, admin: dict = Depends(require_admin)):
    db.delete_user(user_id)
    return {"ok": True}


@app.get("/api/history", response_model=HistoryListResponse)
def api_list_history(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    return list_history(user=user, page=page, page_size=page_size)


if FRONTEND_DIST.exists():
    # Serve compiled Vue SPA with FastAPI so only one process is needed.
    app.mount(
        "/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend"
    )
