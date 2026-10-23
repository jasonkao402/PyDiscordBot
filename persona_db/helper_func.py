from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlite3 import Connection

TWTZ = timezone(timedelta(hours=8))

def split_uid_list(value: str) -> list[int]:
    _res = []
    if not value:
        return _res
    try:
        _res = [int(item) for item in value.split(",") if item.strip()]
    except ValueError:
        # Log the error or handle it as needed
        print(f"Warning: Failed to parse allowed_role_ids from value '{value}'. Returning empty set.")
    return _res


def join_uid_list(values: list[int] | set[int]) -> str:
    return ",".join(str(value) for value in values)


def iso_timestamp() -> str:
    """Get the current time in ISO format with milliseconds precision."""
    return datetime.now(tz=TWTZ).isoformat(timespec="milliseconds")


class SQLiteRepository:
    def __init__(self, conn: Connection):
        self._conn = conn

    @contextmanager
    def connection(self):
        yield self._conn
