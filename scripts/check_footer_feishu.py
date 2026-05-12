#!/usr/bin/env python3
"""Check Hermes runtime-footer config & source support — version-aware.

Detects whether the old (rich) or new (simplified) footer system is installed
and runs appropriate checks.

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
    check("runtime_footer.py exists", False, str(runtime_footer_py))
    sys.exit(1)

# Config checks
check("top-level streaming.enabled", streaming.get("enabled") is True)
check("Feishu platform streaming", feishu.get("streaming") is True)
check("Feishu runtime_footer.enabled", footer.get("enabled") is True)
check("footer excludes Agent field", "agent" not in fields, f"fields={fields}")

if is_new_system:
    # New system: only model, context_pct, cwd are supported
    check("footer includes model", "model" in fields, f"fields={fields}")
    check("footer includes context_pct or context",
          "context_pct" in fields or "context" in fields, f"fields={fields}")
    # Check for unsupported fields (will be silently dropped)
    unsupported = [f for f in fields if f not in ("model", "context_pct", "context", "cwd")]
    for f in unsupported:
        print(f"  ⚠ WARNING: '{f}' not supported by new code — silently ignored")
else:
    # Old system: rich field support
    for field in ["model", "session", "thinking", "context", "tokens"]:
        check(f"footer includes {field}", field in fields, f"fields={fields}")
    check("runtime_footer split function", "def split_runtime_footer" in src)
    check("Feishu interactive card builder",
          "_build_interactive_card_payload" in src or
          (repo / "gateway" / "platforms" / "feishu.py").read_text(encoding="utf-8", errors="ignore").__contains__("split_runtime_footer"))

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
