from uuid import uuid4

import pytest

from app.config import settings
from app.monitoring_repository import MySQLMonitoringRepository

pytestmark = pytest.mark.skipif(settings.storage_backend != "mysql", reason="requires migration-backed MySQL")


def test_monitoring_migration_and_shared_persistence():
    first, second = MySQLMonitoringRepository(), MySQLMonitoringRepository()
    marker = uuid4().hex
    first.mutate(lambda state: state.update(integration_probe=marker))
    try:
        assert second.read()["integration_probe"] == marker
    finally:
        first.mutate(lambda state: state.pop("integration_probe", None))
