#!/usr/bin/env python3
"""Check Hermes Telegram/Discord runtime-footer config & source support — version-aware.

Detects whether the old (rich) or new (simplified) footer system is installed
and runs appropriate checks.

Run from anywhere:
    python ~/.hermes/skills/autonomous-ai-agents/hermes-footer/scripts/check_footer_telegram.py
"""
from __future__ import annotations

from pathlib import Path
import sys

try:
    import yaml
except Exception as exc:
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

# Load config
cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
cfg = cfg or {}
display = cfg.get("display") or {}

# Detect file version
runtime_footer_py = repo / "gateway" / "runtime_footer.py"
is_new_system = False
if runtime_footer_py.exists():
    src = runtime_footer_py.read_text(encoding="utf-8", errors="ignore")
    is_new_system = '_DEFAULT_FIELDS = ("model", "context_pct", "cwd")' in src
    check("runtime_footer.py exists", True, str(runtime_footer_py))
    version = "NEW (simplified)" if is_new_system else "OLD (rich)"
    print(f"  → Detected: {version} footer system")
else:
    check("runtime_footer.py exists", False)
    sys.exit(1)

# Check both Telegram and Discord
for platform_key in ["telegram", "discord"]:
    print(f"\n--- {platform_key} ---")
    plat = ((display.get("platforms") or {}).get(platform_key) or {})
    footer = plat.get("runtime_footer") or {}
    fields = footer.get("fields") or []
    prefix = footer.get("prefix", "")
    separator = footer.get("separator", "")

    check(f"config exists", config_path.exists(), str(config_path))
    check(f"{platform_key} runtime_footer.enabled", footer.get("enabled") is True)

    if is_new_system:
        # New system: only model, context_pct, cwd; separator/prefix ignored
        check(f"footer includes model", "model" in fields, f"fields={fields}")
        check(f"footer includes context_pct or context",
              "context_pct" in fields or "context" in fields, f"fields={fields}")
        if prefix:
            print(f"  ⚠ WARNING: prefix '{prefix}' is ignored by new code")
        if separator:
            print(f"  ⚠ WARNING: separator '{separator}' is ignored by new code")
        unsupported = [f for f in fields if f not in ("model", "context_pct", "context", "cwd")]
        for f in unsupported:
            print(f"  ⚠ WARNING: '{f}' not supported by new code — silently ignored")
    else:
        # Old system: rich field support + prefix/separator
        check(f"{platform_key} has prefix", bool(prefix), f"prefix={repr(prefix)}")
        for field in ["model", "session", "thinking", "context", "tokens"]:
            check(f"footer includes {field}", field in fields, f"fields={fields}")
        check(f"resolve_footer_config supports prefix", '"prefix"' in src or "'prefix'" in src)
        check(f"build_footer_line passes prefix", 'prefix=cfg.get("prefix")' in src or 'prefix=cfg' in src)

if ok:
    print("\nOK: Runtime-footer config/source support looks present.")
    sys.exit(0)
print("\nSome checks failed. Load the hermes-footer skill and follow the repair guide.")
sys.exit(1)
