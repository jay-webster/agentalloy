"""Phase 1 test migration: rename dependency_overrides keys to the new deps providers.

Run from repo root:  python scripts/migrate_phase1_tests.py
Mechanical + safe. After running, fix resulting import errors (the old dummy
providers were deleted) by importing from agentalloy.api.deps, and address any
direct `app.state.` pokes in tests.
"""

import re
from pathlib import Path

TESTS_DIR = Path("tests")

# old override key -> new deps provider
OVERRIDES_MAP = {
    "get_orchestrator": "get_compose_orchestrator",
    "get_retrieve_orchestrator": "get_retrieve_orchestrator",
    "get_skill_store": "get_skill_store",
    "get_orchestrator_for_proxy": "get_compose_orchestrator",
    "get_settings_for_proxy": "get_settings",
    "get_upstream_client": "get_upstream_client",
    "get_embed_client": "get_embed_client",
    "get_embed_async_client": "get_embed_async_client",
    # GOTCHA: proxy's old get_vector_store actually returned the TELEMETRY store.
    "get_vector_store": "get_telemetry_store",
}

changed = []
for py_file in TESTS_DIR.rglob("*.py"):
    content = py_file.read_text()
    original = content
    for old, new in OVERRIDES_MAP.items():
        pattern = r"(\[\s*)" + re.escape(old) + r"(\s*\])"
        content = re.sub(pattern, rf"\1{new}\2", content)
    if content != original:
        py_file.write_text(content)
        changed.append(str(py_file))

for f in changed:
    print(f"✅ migrated overrides in {f}")
print(f"\n{len(changed)} file(s) touched. Now fix imports + app.state pokes, then run pytest.")
