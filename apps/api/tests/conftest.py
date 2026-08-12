import os

# Unit/API tests are deterministic and must not inherit a developer's local
# .env backend. Integration jobs set these variables explicitly before pytest.
os.environ.setdefault("STORAGE_BACKEND", "memory")
os.environ.setdefault("EVENT_BACKEND", "memory")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("REQUIRE_AUTH", "false")
