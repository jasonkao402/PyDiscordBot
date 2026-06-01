from sqlite3 import Connection
from contextlib import contextmanager
from typing import List, Optional
from datetime import datetime

def _split_uid_list(value: str) -> List[int]:
    if not value:
        return []
    return [int(item) for item in value.split(",") if item.strip()]

def _join_uid_list(values: List[int]) -> str:
    return ",".join(str(value) for value in values)

def _now_iso() -> str:
    '''Get the current time in ISO format with milliseconds precision.'''
    return datetime.now().isoformat(timespec="milliseconds")

class SQLiteRepository:
    def __init__(self, conn: Connection):
        self._conn = conn

    @contextmanager
    def connection(self):
        yield self._conn