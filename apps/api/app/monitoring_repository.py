"""Atomic monitoring state, separate from incident/trip/risk repositories.

A single locked workspace keeps ingest, deduplication and review decisions atomic
across API workers. This intentionally small demo retains at most 500 devices,
500 resolved alerts, 1000 run keys, 31 daily reports and 1000 review entries.
"""
from copy import deepcopy
from threading import RLock

from sqlalchemy import select

from .config import settings
from .database.models import MonitoringState
from .database.session import session_factory


class MemoryMonitoringRepository:
    def __init__(self):
        self._payload = {}
        self._lock = RLock()

    def read(self):
        with self._lock:
            return deepcopy(self._payload)

    def mutate(self, operation):
        with self._lock:
            payload = deepcopy(self._payload)
            result = operation(payload)
            self._payload = payload
            return deepcopy(result)


class MySQLMonitoringRepository:
    def __init__(self, factory=None):
        self._factory = factory

    def _session(self):
        return (self._factory or session_factory())()

    def read(self):
        with self._session() as db:
            row = db.get(MonitoringState, "demo")
            if row is None:
                raise RuntimeError("Monitoring migration 0004 has not been applied")
            return deepcopy(row.payload)

    def mutate(self, operation):
        with self._session() as db, db.begin():
            row = db.scalar(select(MonitoringState).where(MonitoringState.id == "demo").with_for_update())
            if row is None:
                raise RuntimeError("Monitoring migration 0004 has not been applied")
            payload = deepcopy(row.payload)
            result = operation(payload)
            row.payload = payload
            return deepcopy(result)


monitoring_repository = (
    MySQLMonitoringRepository() if settings.storage_backend == "mysql" else MemoryMonitoringRepository()
)
