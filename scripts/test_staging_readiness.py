import importlib.util
from pathlib import Path
import sys


MODULE_PATH = Path(__file__).with_name("staging-readiness.py")
SPEC = importlib.util.spec_from_file_location("staging_readiness", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_request_bounds_are_intentionally_small():
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "1 <= args.requests <= 500" in source
    assert "1 <= args.concurrency <= 20" in source


def test_required_security_headers_cover_browser_boundaries():
    assert {"content-security-policy", "x-frame-options", "permissions-policy"} <= MODULE.REQUIRED_HEADERS
