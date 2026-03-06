import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .config import DB_PATH, DEFAULT_STORAGE_QUOTA_BYTES, DEFAULT_UPLOAD_RATE_BYTES_SEC


class Database:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def conn(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _init_db(self):
        with self.conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    storage_quota_bytes INTEGER NOT NULL,
                    upload_rate_bytes_sec INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS upload_tasks (
                    upload_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL DEFAULT '',
                    file_name TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    file_hash TEXT NOT NULL,
                    chunk_size INTEGER NOT NULL,
                    total_chunks INTEGER NOT NULL,
                    uploaded_chunks TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS files (
                    file_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL DEFAULT '',
                    file_name TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    file_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS upload_history (
                    record_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    file_hash TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

            self._ensure_column(conn, "upload_tasks", "user_id", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "files", "user_id", "TEXT NOT NULL DEFAULT ''")

    @staticmethod
    def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str):
        cur = conn.execute(f"PRAGMA table_info({table})")
        cols = [row[1] for row in cur.fetchall()]
        if column not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    def create_user(self, row: Dict[str, Any]):
        with self.conn() as conn:
            conn.execute(
                """
                INSERT INTO users (user_id, username, password_hash, storage_quota_bytes, upload_rate_bytes_sec, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    row["user_id"],
                    row["username"],
                    row["password_hash"],
                    row.get("storage_quota_bytes", DEFAULT_STORAGE_QUOTA_BYTES),
                    row.get("upload_rate_bytes_sec", DEFAULT_UPLOAD_RATE_BYTES_SEC),
                    row["created_at"],
                ),
            )

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        with self.conn() as conn:
            cur = conn.execute("SELECT * FROM users WHERE username = ? LIMIT 1", (username,))
            row = cur.fetchone()
            return dict(row) if row else None

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        with self.conn() as conn:
            cur = conn.execute("SELECT * FROM users WHERE user_id = ? LIMIT 1", (user_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def sum_user_file_size(self, user_id: str) -> int:
        with self.conn() as conn:
            cur = conn.execute("SELECT COALESCE(SUM(file_size), 0) AS total FROM files WHERE user_id = ?", (user_id,))
            row = cur.fetchone()
            return int(row["total"] if row and row["total"] is not None else 0)

    def sum_user_pending_upload_size(self, user_id: str) -> int:
        with self.conn() as conn:
            cur = conn.execute(
                """
                SELECT COALESCE(SUM(file_size), 0) AS total
                FROM upload_tasks
                WHERE user_id = ?
                """,
                (user_id,),
            )
            row = cur.fetchone()
            return int(row["total"] if row and row["total"] is not None else 0)

    def upsert_upload_task(self, row: Dict[str, Any]):
        with self.conn() as conn:
            conn.execute(
                """
                INSERT INTO upload_tasks (
                    upload_id, user_id, file_name, file_size, file_hash, chunk_size,
                    total_chunks, uploaded_chunks, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(upload_id) DO UPDATE SET
                    user_id=excluded.user_id,
                    file_name=excluded.file_name,
                    file_size=excluded.file_size,
                    file_hash=excluded.file_hash,
                    chunk_size=excluded.chunk_size,
                    total_chunks=excluded.total_chunks,
                    uploaded_chunks=excluded.uploaded_chunks,
                    status=excluded.status,
                    updated_at=excluded.updated_at
                """,
                (
                    row["upload_id"],
                    row["user_id"],
                    row["file_name"],
                    row["file_size"],
                    row["file_hash"],
                    row["chunk_size"],
                    row["total_chunks"],
                    json.dumps(row["uploaded_chunks"]),
                    row["status"],
                    row["created_at"],
                    row["updated_at"],
                ),
            )

    def get_upload_task(self, upload_id: str) -> Optional[Dict[str, Any]]:
        with self.conn() as conn:
            cur = conn.execute("SELECT * FROM upload_tasks WHERE upload_id = ?", (upload_id,))
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_upload_task(row)

    def get_upload_task_by_hash(self, user_id: str, file_hash: str) -> Optional[Dict[str, Any]]:
        with self.conn() as conn:
            cur = conn.execute(
                """
                SELECT * FROM upload_tasks
                WHERE user_id = ? AND file_hash = ? AND status != 'completed'
                ORDER BY updated_at DESC LIMIT 1
                """,
                (user_id, file_hash),
            )
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_upload_task(row)

    def update_uploaded_chunks(self, upload_id: str, uploaded_chunks: Iterable[int], status: str, updated_at: str):
        with self.conn() as conn:
            conn.execute(
                "UPDATE upload_tasks SET uploaded_chunks = ?, status = ?, updated_at = ? WHERE upload_id = ?",
                (json.dumps(sorted(set(uploaded_chunks))), status, updated_at, upload_id),
            )

    def add_uploaded_chunk(self, upload_id: str, chunk_index: int, updated_at: str) -> Dict[str, Any]:
        with self.conn() as conn:
            cur = conn.execute(
                "SELECT uploaded_chunks, total_chunks FROM upload_tasks WHERE upload_id = ? LIMIT 1",
                (upload_id,),
            )
            row = cur.fetchone()
            if not row:
                raise ValueError("upload task not found")

            uploaded = set(json.loads(row["uploaded_chunks"]))
            uploaded.add(int(chunk_index))
            total_chunks = int(row["total_chunks"])
            status = "uploaded" if len(uploaded) == total_chunks else "uploading"

            conn.execute(
                "UPDATE upload_tasks SET uploaded_chunks = ?, status = ?, updated_at = ? WHERE upload_id = ?",
                (json.dumps(sorted(uploaded)), status, updated_at, upload_id),
            )
            return {
                "uploaded_chunks": sorted(uploaded),
                "status": status,
                "total_chunks": total_chunks,
            }

    def delete_upload_task(self, upload_id: str):
        with self.conn() as conn:
            conn.execute("DELETE FROM upload_tasks WHERE upload_id = ?", (upload_id,))

    def insert_file(self, row: Dict[str, Any]):
        with self.conn() as conn:
            conn.execute(
                """
                INSERT INTO files (file_id, user_id, file_name, file_path, file_size, file_hash, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["file_id"],
                    row["user_id"],
                    row["file_name"],
                    row["file_path"],
                    row["file_size"],
                    row["file_hash"],
                    row["created_at"],
                ),
            )

    def get_file_by_hash(self, user_id: str, file_hash: str) -> Optional[Dict[str, Any]]:
        with self.conn() as conn:
            cur = conn.execute(
                "SELECT * FROM files WHERE user_id = ? AND file_hash = ? LIMIT 1",
                (user_id, file_hash),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def get_file_by_id(self, user_id: str, file_id: str) -> Optional[Dict[str, Any]]:
        with self.conn() as conn:
            cur = conn.execute("SELECT * FROM files WHERE user_id = ? AND file_id = ? LIMIT 1", (user_id, file_id))
            row = cur.fetchone()
            return dict(row) if row else None

    def list_files(self, user_id: str) -> List[Dict[str, Any]]:
        with self.conn() as conn:
            cur = conn.execute("SELECT * FROM files WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
            return [dict(row) for row in cur.fetchall()]

    def delete_file(self, user_id: str, file_id: str):
        with self.conn() as conn:
            conn.execute("DELETE FROM files WHERE user_id = ? AND file_id = ?", (user_id, file_id))

    def insert_upload_history(self, row: Dict[str, Any]):
        with self.conn() as conn:
            conn.execute(
                """
                INSERT INTO upload_history (
                    record_id, user_id, file_name, file_size, file_hash, status, message, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["record_id"],
                    row["user_id"],
                    row["file_name"],
                    row["file_size"],
                    row["file_hash"],
                    row["status"],
                    row["message"],
                    row["created_at"],
                ),
            )

    def list_upload_history(self, user_id: str, page: int, page_size: int) -> Dict[str, Any]:
        offset = (page - 1) * page_size
        with self.conn() as conn:
            count_row = conn.execute(
                "SELECT COUNT(1) AS total FROM upload_history WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            total = int(count_row["total"] if count_row else 0)
            rows = conn.execute(
                """
                SELECT * FROM upload_history
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (user_id, page_size, offset),
            ).fetchall()
            return {"items": [dict(row) for row in rows], "total": total}

    @staticmethod
    def _row_to_upload_task(row: sqlite3.Row) -> Dict[str, Any]:
        record = dict(row)
        record["uploaded_chunks"] = json.loads(record["uploaded_chunks"])
        return record


db = Database(DB_PATH)
