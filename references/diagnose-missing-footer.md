# Diagnose Missing Runtime Footer

Use this reference when the user reports that the Hermes runtime footer has disappeared on a platform (Telegram, Feishu, Discord, etc.) despite being previously configured.

> Current reality for this environment: the active footer implementation is the **rich-field** system with `_RUNTIME_FOOTER_LABELS`, configurable `separator`/`prefix`, and support for `session`, `thinking`, `context`, `tokens`, `usage`, `time`, `cost`, and `cwd`.

## Quick triage

| Symptom | Most likely cause |
|---------|-------------------|
| Footer missing on **all** platforms | Agent 429 / API rate-limit errors; `/footer off` toggled global; gateway not restarted after config change |
| Footer missing on **one** platform | Per-platform config issue; streaming path failure; platform adapter edit failure |
| Discord footer sent as **separate message** in streaming | Expected behavior — `_try_embed_stream_footer_in_place` does not support Discord (only Feishu/Telegram) |
| Footer missing **after config/code change** | Config caching; gateway restart needed; config YAML syntax error |
| Footer value is wrong (for example `Session` vs `CWD`) | Wrong field list in per-platform `runtime_footer.fields` |
| Footer was working, now gone after API 429 | The agent returned an error response — footer only added for **successful** responses |

## First: verify the live footer code

```bash
cd ~/.hermes/hermes-agent
python3 - <<'PY'
from pathlib import Path
text = Path('gateway/runtime_footer.py').read_text(encoding='utf-8')
print('_RUNTIME_FOOTER_LABELS' in text)
print('"cwd": "CWD"' in text)
print('"cost": "Cost"' in text)
PY
```

If those markers are present, treat the system as rich-footer and debug config/runtime behavior directly.

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

**Critical check**: Verify that each platform's `fields` list matches the behavior the user wants. For this user's current standard on Feishu / Telegram / Discord, the expected order is:

```yaml
fields: [model, cwd, thinking, context, tokens, cost, usage]
```

So the second slot should contain `cwd` rather than `session`.

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

## Common pitfalls

- **The try/except in `_respond_final`** catches ALL exceptions and sets `_footer_line = ""`. Any error → no footer, no user-facing error.
- **Gateway restart is required** after config or code changes, because config may be cached.
- **Per-platform field order controls the visible footer** — if a user wants `CWD` where `Session` currently appears, replace that field in the platform's `runtime_footer.fields` list, and keep all target platforms aligned.
- **Discord streaming often uses a separate footer message** — that's expected when in-place edit embedding is not supported there.
- **The `/footer` slash command** toggles `display.runtime_footer.enabled` globally; per-platform overrides can still differ.
