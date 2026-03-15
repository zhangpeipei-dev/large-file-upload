from typing import List, Optional

from pydantic import BaseModel, Field


class InitUploadRequest(BaseModel):
    file_name: str = Field(..., min_length=1)
    file_size: int = Field(..., gt=0)
    file_hash: str = Field(..., min_length=16)
    chunk_size: int = Field(..., gt=0)
    group_id: Optional[str] = None
    group_name: Optional[str] = None
    group_total_files: Optional[int] = None
    group_total_size: Optional[int] = None


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
    password: str = Field(..., min_length=5, max_length=128)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=5, max_length=128)


class UserInfo(BaseModel):
    user_id: str
    username: str
    role: str
    storage_quota_bytes: int
    upload_rate_bytes_sec: int
    created_at: Optional[str] = None


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
    group_id: Optional[str] = None
    is_group: Optional[int] = None


class HistoryListResponse(BaseModel):
    items: List[HistoryItem]
    total: int
    page: int
    page_size: int


class CompleteGroupRequest(BaseModel):
    group_id: str = Field(..., min_length=6)
    group_name: str = Field(..., min_length=1)
    group_total_files: int = Field(..., gt=0)
    group_total_size: int = Field(..., gt=0)
    status: str = Field(..., min_length=1)
    message: Optional[str] = None


class CompleteGroupResponse(BaseModel):
    ok: bool


class ZipFilesRequest(BaseModel):
    file_ids: List[str] = Field(..., min_length=1)
