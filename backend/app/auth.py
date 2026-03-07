import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import (
    DEFAULT_STORAGE_QUOTA_BYTES,
    DEFAULT_UPLOAD_RATE_BYTES_SEC,
    JWT_ALGORITHM,
    JWT_EXPIRE_HOURS,
    JWT_SECRET,
)
from .db import db

bearer_scheme = HTTPBearer(auto_error=False)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120000)
    return f"{salt.hex()}:{digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        salt_hex, digest_hex = encoded.split(":", 1)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except Exception:
        return False
    current = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120000)
    return hmac.compare_digest(current, expected)


def create_token(user_id: str, username: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS)
    payload = {
        "sub": user_id,
        "username": username,
        "exp": exp,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token"
        ) from exc


def ensure_admin_user():
    admin_username = "admin"
    admin = db.get_user_by_username(admin_username)
    if not admin:
        user = {
            "user_id": uuid4().hex,
            "username": admin_username,
            "password_hash": hash_password("adminadmin"),
            "storage_quota_bytes": DEFAULT_STORAGE_QUOTA_BYTES,
            "upload_rate_bytes_sec": DEFAULT_UPLOAD_RATE_BYTES_SEC,
            "role": "admin",
            "created_at": utc_now(),
        }
        db.create_user(user)


def register_user(username: str, password: str) -> dict:
    if db.get_user_by_username(username):
        raise HTTPException(status_code=400, detail="username already exists")

    user = {
        "user_id": uuid4().hex,
        "username": username,
        "password_hash": hash_password(password),
        "storage_quota_bytes": DEFAULT_STORAGE_QUOTA_BYTES,
        "upload_rate_bytes_sec": DEFAULT_UPLOAD_RATE_BYTES_SEC,
        "role": "pending",
        "created_at": utc_now(),
    }
    db.create_user(user)
    return {
        "user_id": user["user_id"],
        "username": username,
        "storage_quota_bytes": user["storage_quota_bytes"],
        "upload_rate_bytes_sec": user["upload_rate_bytes_sec"],
    }


def login_user(username: str, password: str) -> dict:
    user = db.get_user_by_username(username)
    if not user or not verify_password(password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="username or password is incorrect")

    role = user.get("role", "user")
    if role == "pending":
        raise HTTPException(status_code=403, detail="account pending approval")

    token = create_token(user["user_id"], user["username"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "user_id": user["user_id"],
            "username": user["username"],
            "role": role,
            "storage_quota_bytes": user["storage_quota_bytes"],
            "upload_rate_bytes_sec": user["upload_rate_bytes_sec"],
        },
    }


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    if not credentials:
        raise HTTPException(status_code=401, detail="missing bearer token")

    payload = decode_token(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="invalid token payload")

    user = db.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="user not found")
    return user


def get_user_quota(user: dict) -> dict:
    used_files_bytes = db.sum_user_file_size(user["user_id"])
    used_uploading_bytes = db.sum_user_pending_upload_size(user["user_id"])
    quota = int(user["storage_quota_bytes"])
    return {
        "storage_quota_bytes": quota,
        "used_files_bytes": used_files_bytes,
        "used_uploading_bytes": used_uploading_bytes,
        "available_bytes": max(quota - used_files_bytes - used_uploading_bytes, 0),
        "upload_rate_bytes_sec": int(user["upload_rate_bytes_sec"]),
    }


def require_admin(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="admin privileges required")
    return user
