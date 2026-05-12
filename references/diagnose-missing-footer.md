# Diagnose Missing Runtime Footer

Use this reference when the user reports that the Hermes runtime footer has disappeared on a platform (Telegram, Feishu, Discord, etc.) despite being previously configured.

## Quick triage

| Symptom | Most likely cause |
|---------|-------------------|
| Footer missing on **all** platforms | Agent 429 / API rate-limit errors; `/footer off` toggled global; **OR post-update field mismatch (most common)** |
| Footer missing on **one** platform | Per-platform config issue; streaming path failure; platform adapter edit failure |
| Discord footer sent as **separate message** in streaming | Expected behavior — `_try_embed_stream_footer_in_place` does not support Discord (only Feishu/Telegram) |
| Footer missing **after config/code change** | Config caching; gateway restart needed; config YAML syntax error |
| Footer missing **after `hermes update`** | **Most likely: code rewrite removed old field names** — config references `session`, `thinking`, `tokens`, `usage` but new code only supports `model`, `context_pct`, `cwd` |
| Footer was working, now gone after API 429 | The agent returned an error response — footer only added for **successful** responses |

## First: detect which version of runtime_footer.py

```bash
cd ~/.hermes/hermes-agent
head -35 gateway/runtime_footer.py
```

**Old system**: has `_RUNTIME_FOOTER_LABELS` dict with entries like `"model"`, `"session"`, `"thinking"`, etc., and `format_runtime_footer()` with many field branches.

**New system (post-May 2026 rewrite)**: has `_DEFAULT_FIELDS = ("model", "context_pct", "cwd")`, simple `format_runtime_footer()` with only 3 `elif` branches.

This determines the diagnostic path below.

## Diagnostic checklist

### 1. Verify config resolution

```python
from hermes_cli.config import read_raw_config
from gateway.runtime_footer import resolve_footer_config

config = read_raw_config()
for platform in ["telegram", "feishu", "discord"]:
    cfg = resolve_footer_config(config, platform)
    print(f"{platform}: enabled={cfg['enabled']}, fields={cfg['fields']}")
```

**Config merge order** (later wins):
1. Built-in defaults (`enabled=False`, fields=`model,context_pct,cwd`)
2. `display.runtime_footer` — global settings
3. `display.platforms.<name>.runtime_footer` — per-platform overrides

Even if `display.runtime_footer.enabled: false`, a per-platform `enabled: true` should override.

**Critical check (new system)**: If `fields` contains `session`, `thinking`, `tokens`, `usage`, `time` — these are **unknown to new code** and silently dropped. Only `model` and `context_pct` (also accepts `context`) and `cwd` will render. This is the #1 cause of "footer disappeared after update".

### 2. Check gateway logs for footer activity

```bash
journalctl --user -u hermes-gateway --since "30 min ago" --no-pager | grep -i -E "footer built|runtime_footer|stream footer" | tail -20
```

No "footer built" lines at all → the try/except in `_respond_final` caught an error, or footer function returned empty string. Also check for the debug log:
```bash
journalctl --user -u hermes-gateway --since "30 min ago" --no-pager | grep "runtime_footer build failed"
```

Also check for 429 errors that prevent agent responses entirely:
```bash
journalctl --user -u hermes-gateway --since "30 min ago" --no-pager | grep -i "429\|rate_limit"
```

### 3. Test standalone footer building

**New system (post-May 2026)**:
```python
from hermes_cli.config import read_raw_config
from gateway.runtime_footer import build_footer_line

config = read_raw_config()
footer = build_footer_line(
    user_config=config,
    platform_key="telegram",
    model="deepseek-v4-flash",
    context_tokens=12345,
    context_length=200000,
    cwd="/home/momo",
)
print(repr(footer))
```

**Old system (pre-May 2026)**:
```python
from hermes_cli.config import read_raw_config
from gateway.runtime_footer import build_footer_line

config = read_raw_config()
footer = build_footer_line(
    user_config=config,
    platform_key="telegram",
    model="gpt-5.4",
    provider="openai-codex",
    context_tokens=12345,
    context_length=200000,
    session_id="test_session",
    reasoning_config={"effort": "medium"},
    input_tokens=1200,
    output_tokens=567,
    account_usage=None,
    elapsed_seconds=12.3,
)
print(repr(footer))
```

If this returns `""`, the issue is in config resolution or code. If it returns valid text, the runtime has a different problem.

### 4. Distinguish response types

Footers only appear on **successful agent responses** via `_respond_final`. No-footer scenarios:

| Message type | Footer? |
|---|---|
| Agent response (non-streaming) | ✅ Appended to response text |
| Agent response (streaming) | ✅ Edited in-place or sent as separate message |
| Agent error (429, timeout) | ❌ Error path skips footer entirely |
| Tool-generated message (`send_message`) | ❌ Bypasses `_respond_final` |
| Slash command response | ❌ Depends on command |

### 5. Verify `/footer` toggle state

```bash
hermes config get display.runtime_footer.enabled
```

If `false`, run `/footer on` in any platform or:
```bash
hermes config set display.runtime_footer.enabled true
hermes gateway restart
```

### 6. Check the code path (if config is correct but no footer)

Look at the exact `_respond_final` block in `gateway/run.py`:
```bash
grep -n "build_footer_line\|_footer_line\|runtime_footer" /home/momo/.hermes/hermes-agent/gateway/run.py | head -10
```

Check what arguments are actually being passed. The most common new-system failure: the call passes only 4 params, so anything besides `model` and `context_pct`/`cwd` is missing.

## Key source files

| File | Role |
|------|------|
| `gateway/runtime_footer.py` | Footer building — check for old (rich) vs new (limited) version |
| `gateway/run.py` `_respond_final()` | Footer assembly and appending (~L7635+) |
| `~/.hermes/config.yaml` | Footer configuration |

## Common pitfalls (new system)

- **Unknown fields are silently dropped** — `session`, `thinking`, `tokens`, `usage`, `time` in config produce NO error and NO footer content for those fields. Only `model`, `context_pct`/`context`, `cwd` work.
- **The try/except in `_respond_final`** catches ALL exceptions and sets `_footer_line = ""`. Any error → no footer, no user-facing error.
- **`_bfl()` call in new code takes only 4 payload params** — if you extend it, check both `runtime_footer.py` AND `run.py` call site.
- **The `separator` key in config is ignored by new system** — hardcoded to ` · ` (middle dot).
- **The `prefix` key in config is ignored by new system** — no divider line.
