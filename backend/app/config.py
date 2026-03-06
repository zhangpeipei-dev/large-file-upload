import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_TMP_DIR = DATA_DIR / "tmp_chunks"
FILE_STORAGE_DIR = DATA_DIR / "files"
DB_PATH = DATA_DIR / "uploads.db"

DEFAULT_CHUNK_SIZE = 8 * 1024 * 1024  # 8MB
MAX_CHUNK_SIZE = 64 * 1024 * 1024  # 64MB
MAX_CONCURRENCY = 4

JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "12"))

DEFAULT_STORAGE_QUOTA_BYTES = int(os.getenv("DEFAULT_STORAGE_QUOTA_BYTES", str(50 * 1024 * 1024 * 1024)))
DEFAULT_UPLOAD_RATE_BYTES_SEC = int(os.getenv("DEFAULT_UPLOAD_RATE_BYTES_SEC", str(100 * 1024 * 1024)))

for directory in (DATA_DIR, UPLOAD_TMP_DIR, FILE_STORAGE_DIR):
    directory.mkdir(parents=True, exist_ok=True)
