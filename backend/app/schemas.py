from typing import List, Optional

from pydantic import BaseModel, Field


class InitUploadRequest(BaseModel):
    file_name: str = Field(..., min_length=1)
    file_size: int = Field(..., gt=0)
    file_hash: str = Field(..., min_length=16)
    chunk_size: int = Field(..., gt=0)


class InitUploadResponse(BaseModel):
    upload_id: Optional[str] = None
    file_exists: bool = False
    file_id: Optional[str] = None
    uploaded_chunks: List[int] = []
    total_chunks: int
    chunk_size: int


class UploadStatusResponse(BaseModel):
    upload_id: str
    file_name: str
    file_size: int
    file_hash: str
    chunk_size: int
    total_chunks: int
    uploaded_chunks: List[int]
    status: str


class MergeRequest(BaseModel):
    upload_id: str


class MergeResponse(BaseModel):
    file_id: str
    file_name: str
    file_size: int
    file_hash: str


class FileItem(BaseModel):
    file_id: str
    file_name: str
    file_size: int
    file_hash: str
    created_at: str


class HealthResponse(BaseModel):
    status: str


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)


class UserInfo(BaseModel):
    user_id: str
    username: str
    storage_quota_bytes: int
    upload_rate_bytes_sec: int


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserInfo


class QuotaResponse(BaseModel):
    storage_quota_bytes: int
    used_files_bytes: int
    used_uploading_bytes: int
    available_bytes: int
    upload_rate_bytes_sec: int


class HistoryItem(BaseModel):
    record_id: str
    user_id: str
    file_name: str
    file_size: int
    file_hash: str
    status: str
    message: str
    created_at: str


class HistoryListResponse(BaseModel):
    items: List[HistoryItem]
    total: int
    page: int
    page_size: int
