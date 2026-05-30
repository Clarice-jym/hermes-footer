#!/usr/bin/env python3
"""Check Hermes Telegram/Discord runtime-footer config against the current rich-footer setup.

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

# Detect rich-footer support
runtime_footer_py = repo / "gateway" / "runtime_footer.py"
if runtime_footer_py.exists():
    src = runtime_footer_py.read_text(encoding="utf-8", errors="ignore")
    check("runtime_footer.py exists", True, str(runtime_footer_py))
    rich_markers = [
        '"cwd": "CWD"',
        '"cost": "Cost"',
        '"usage": "Usage"',
        '"thinking": "Thinking"',
    ]
    check(
        "rich footer markers present",
        all(marker in src for marker in rich_markers),
        "expects CWD/Cost/Usage/Thinking labels",
    )
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
    expected_fields = ["model", "cwd", "thinking", "context", "tokens", "cost", "usage"]
    check(f"{platform_key} preferred field order", fields == expected_fields, f"fields={fields}")
    check(f"{platform_key} separator is preferred pipe", separator == " | ", f"separator={separator!r}")
    check(f"{platform_key} keeps divider prefix", bool(prefix), f"prefix={repr(prefix)}")
    check(f"resolve_footer_config supports prefix", '"prefix"' in src or "'prefix'" in src)
    check(f"build_footer_line passes prefix", 'prefix=cfg.get("prefix"' in src or 'prefix=cfg' in src)

if ok:
    print("\nOK: Runtime-footer config/source support looks present.")
    sys.exit(0)
print("\nSome checks failed. Load the hermes-footer skill and follow the repair guide.")
sys.exit(1)
