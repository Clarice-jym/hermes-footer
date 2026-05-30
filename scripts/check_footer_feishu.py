#!/usr/bin/env python3
"""Check Hermes Feishu runtime-footer config against the current rich-footer setup.

Run from anywhere:
    python ~/.hermes/skills/autonomous-ai-agents/hermes-footer/scripts/check_footer_feishu.py
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
streaming = cfg.get("streaming") or {}
display = cfg.get("display") or {}
feishu = ((display.get("platforms") or {}).get("feishu") or {})
footer = feishu.get("runtime_footer") or {}
fields = footer.get("fields") or []

check("config exists", config_path.exists(), str(config_path))

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
    check("runtime_footer.py exists", False, str(runtime_footer_py))
    sys.exit(1)

# Config checks
check("top-level streaming.enabled", streaming.get("enabled") is True)
check("Feishu platform streaming", feishu.get("streaming") is True)
check("Feishu runtime_footer.enabled", footer.get("enabled") is True)
check("footer excludes Agent field", "agent" not in fields, f"fields={fields}")
check("Feishu separator is preferred pipe", footer.get("separator") == " | ", f"separator={footer.get('separator')!r}")
expected_fields = ["model", "cwd", "thinking", "context", "tokens", "cost", "usage"]
check("Feishu preferred field order", fields == expected_fields, f"fields={fields}")
check("Feishu keeps no divider prefix", not footer.get("prefix"), f"prefix={footer.get('prefix')!r}")
check("runtime_footer split function", "def split_runtime_footer" in src)

# Gateway embedding check
run_py = repo / "gateway" / "run.py"
if run_py.exists():
    run_src = run_py.read_text(encoding="utf-8", errors="ignore")
    check("Gateway in-place stream footer embedding",
          "_try_embed_stream_footer_in_place" in run_src)

if ok:
    print("\nOK: Feishu streaming + footer config/source support looks present.")
    sys.exit(0)
print("\nSome checks failed. Load the hermes-footer skill and follow the repair guide.")
sys.exit(1)
