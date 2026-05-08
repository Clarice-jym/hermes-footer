#!/usr/bin/env python3
"""Check Hermes Feishu streaming + runtime-footer config/source support.

Run from anywhere:
    python ~/.hermes/skills/autonomous-ai-agents/hermes-footer/scripts/check_footer_feishu.py
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
streaming = cfg.get("streaming") or {}
display = cfg.get("display") or {}
feishu = ((display.get("platforms") or {}).get("feishu") or {})
footer = feishu.get("runtime_footer") or {}
fields = footer.get("fields") or []

check("config exists", config_path.exists(), str(config_path))
check("top-level streaming.enabled", streaming.get("enabled") is True)
check("Feishu platform streaming", feishu.get("streaming") is True)
check("Feishu runtime_footer.enabled", footer.get("enabled") is True)
check("footer excludes Agent field", "agent" not in fields, f"fields={fields}")
for field in ["model", "session", "thinking", "context", "tokens"]:
    check(f"footer includes {field}", field in fields, f"fields={fields}")

files = {
    "runtime_footer": repo / "gateway" / "runtime_footer.py",
    "feishu": repo / "gateway" / "platforms" / "feishu.py",
    "run": repo / "gateway" / "run.py",
    "stream_consumer": repo / "gateway" / "stream_consumer.py",
}
texts = {name: path.read_text(encoding="utf-8", errors="ignore") if path.exists() else "" for name, path in files.items()}
check("Hermes source checkout exists", repo.exists(), str(repo))
check("runtime_footer split function", "def split_runtime_footer" in texts["runtime_footer"])
check("Feishu imports split_runtime_footer", "split_runtime_footer" in texts["feishu"])
check("Feishu interactive card builder", "_build_interactive_card_payload" in texts["feishu"])
check("Gateway in-place stream footer embedding", "_try_embed_stream_footer_in_place" in texts["run"])

if ok:
    print("\nOK: Feishu streaming + footer config/source support looks present.")
    sys.exit(0)
print("\nSome checks failed. Load the hermes-footer skill (Feishu section) and follow the repair guide.")
sys.exit(1)
