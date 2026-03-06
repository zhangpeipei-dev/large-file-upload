from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .auth import get_current_user, get_user_quota, login_user, register_user
from .schemas import (
    FileItem,
    HealthResponse,
    HistoryListResponse,
    InitUploadRequest,
    InitUploadResponse,
    LoginRequest,
    LoginResponse,
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
    init_upload,
    list_history,
    list_files,
    merge_chunks,
    save_chunk,
    status,
)

app = FastAPI(title="Large File Upload Service", version="1.1.0")
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
    await save_chunk(user=user, upload_id=upload_id, chunk_index=chunk_index, chunk_data=chunk)
    return {"ok": True}


@app.post("/api/uploads/merge", response_model=MergeResponse)
def api_merge(payload: MergeRequest, user: dict = Depends(get_current_user)):
    return merge_chunks(user=user, upload_id=payload.upload_id)


@app.get("/api/files", response_model=list[FileItem])
def api_list_files(user: dict = Depends(get_current_user)):
    return list_files(user=user)


@app.get("/api/files/{file_id}/download")
def api_download_file(file_id: str, user: dict = Depends(get_current_user)):
    record = get_file(user=user, file_id=file_id)
    return FileResponse(record["file_path"], filename=record["file_name"], media_type="application/octet-stream")


@app.delete("/api/files/{file_id}")
def api_delete_file(file_id: str, user: dict = Depends(get_current_user)):
    delete_file(user=user, file_id=file_id)
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
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
