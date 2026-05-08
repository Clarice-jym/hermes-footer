#!/usr/bin/env python3
"""Check Hermes Telegram runtime-footer config/source support.

Run from anywhere:
    python ~/.hermes/skills/autonomous-ai-agents/hermes-footer/scripts/check_footer_telegram.py
"""
from __future__ import annotations

from pathlib import Path
import sys

try:
    import yaml
except Exception as exc:  # pragma: no cover
    print(f"FAIL: PyYAML unavailable: {exc}")
    sys.exit(2)

home = Path.home() / ".hermes"
config_path = home / "config.yaml"
repo = home / "hermes-agent"

ok = True

def check(name: str, condition: bool, detail: str = "") -> None:
    global ok
    status = "PASS" if condition else "FAIL"
    print(f"{status}: {name}{(' — ' + detail) if detail else ''}")
    ok = ok and condition

cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
cfg = cfg or {}
display = cfg.get("display") or {}
telegram = ((display.get("platforms") or {}).get("telegram") or {})
footer = telegram.get("runtime_footer") or {}
fields = footer.get("fields") or []
prefix = footer.get("prefix", "")

check("config exists", config_path.exists(), str(config_path))
check("Telegram runtime_footer.enabled", footer.get("enabled") is True)
check("Telegram has prefix", bool(prefix), f"prefix={repr(prefix)}")
for field in ["model", "session", "thinking", "context", "tokens", "time"]:
    check(f"footer includes {field}", field in fields, f"fields={fields}")

# Source check: build_footer_line and resolve_footer_config must support prefix
runtime_footer_py = repo / "gateway" / "runtime_footer.py"
if runtime_footer_py.exists():
    src = runtime_footer_py.read_text(encoding="utf-8", errors="ignore")
    check("runtime_footer.py exists", True, str(runtime_footer_py))
    check("resolve_footer_config supports prefix", '"prefix"' in src or "'prefix'" in src)
    check("build_footer_line passes prefix", 'prefix=cfg.get("prefix")' in src or 'prefix=cfg' in src)
else:
    check("runtime_footer.py exists", False)

if ok:
    print("\nOK: Telegram runtime-footer config/source support looks present.")
    sys.exit(0)
print("\nSome checks failed. Load the hermes-footer skill (Telegram section) and follow the repair guide.")
sys.exit(1)
