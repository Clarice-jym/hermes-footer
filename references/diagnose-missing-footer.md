# Diagnose Missing Runtime Footer

Use this reference when the user reports that the Hermes runtime footer has disappeared on a platform (Telegram, Feishu, etc.) despite being previously configured.

## Quick triage

| Symptom | Most likely cause |
|---------|-------------------|
| Footer missing on **all** platforms | Agent 429 / API rate-limit errors preventing normal response generation; `/footer off` toggled global `enabled` to `false` |
| Footer missing on **one** platform (e.g. Telegram but not Feishu) | Per-platform config issue; streaming path failure; platform adapter edit failure |
| Footer missing **after config/code change** | Config caching; gateway restart needed; config YAML syntax error |
| Footer missing only when **streaming** | `_try_embed_stream_footer_in_place` failure; response + footer exceeds message length limit |
| Footer was working, now gone after API 429 | The agent returned an error response — the footer code path is only reached for **successful** responses |

## Diagnostic checklist

### 1. Verify config resolution

Run the same path the gateway uses:

```python
from hermes_cli.config import read_raw_config
from gateway.runtime_footer import resolve_footer_config

config = read_raw_config()
for platform in ["telegram", "feishu"]:
    cfg = resolve_footer_config(config, platform)
    print(f"{platform}: enabled={cfg['enabled']}, fields={cfg['fields']}")
```

Expected output: `enabled=True` with the expected `fields` list.

**Config merge order** (later wins):
1. Built-in defaults (`enabled=False`)
2. `display.runtime_footer` — global settings
3. `display.platforms.<name>.runtime_footer` — per-platform overrides

So even if `display.runtime_footer.enabled: false`, a per-platform `enabled: true` should override.

### 2. Check gateway status & logs

```bash
systemctl --user status hermes-gateway --no-pager -l
journalctl --user -u hermes-gateway --since "30 min ago" --no-pager | grep -i -E "footer|usage|runtime_footer|429|error"
cat ~/.hermes/logs/gateway.log | grep -i -E "footer|runtime_footer" | tail -20
```

Look for:
- 429 errors (usage limit reached) — these cause the agent to fail, producing no footer
- Footer-related errors (rare, but can happen if `fetch_account_usage` throws)
- Gateway not running / restarted recently

### 3. Test standalone footer building

Simulate the exact code path from `_respond_final`:

```python
from hermes_cli.config import read_raw_config
from gateway.runtime_footer import build_footer_line

config = read_raw_config()
footer = build_footer_line(
    user_config=config,
    platform_key="telegram",   # or "feishu"
    model="gpt-5.4",
    provider="openai-codex",
    context_tokens=12345,
    context_length=200000,
    session_id="test_session",
    reasoning_config={"effort": "medium"},
    input_tokens=1200,
    output_tokens=567,
    account_usage=None,        # simulate failed fetch_usage
    elapsed_seconds=12.3,
)
print(repr(footer))
```

If this returns empty string, the issue is in the config or code. If it returns a valid footer, the runtime has a different issue.

### 4. Distinguish response types

Footers are only appended to **successful agent responses** via `_respond_final` (in `gateway/run.py`). Messages that can lack footers:

| Message type | Footer behavior |
|---|---|
| Agent response (non-streaming) | Footer appended directly to response text |
| Agent response (streaming) | Footer held back, then edited in-place or sent as separate message |
| Agent error response (429, timeout) | No footer — error path skips footer code entirely |
| Tool-generated message (`send_message`) | No footer — bypasses `_respond_final` entirely |
| Slash command response | Depends on command — some bypass `_respond_final` |

### 5. Check the streaming path

If the platform uses streaming (`streaming: true`):

1. The agent response is sent incrementally as it's generated
2. After generation completes, `_respond_final` tries `_try_embed_stream_footer_in_place()` to edit the last message in-place
3. If that fails, it falls back to sending the footer as a **separate trailing message**
4. If both fail, the footer is silently dropped

Common streaming footer failures:
- Combined response + footer exceeds Telegram's 4096 UTF-16 char limit → fallback to separate message
- Feishu card edit fails → fallback to separate message
- Adapter `edit_message()` doesn't support metadata → Feishu card metadata lost

### 6. Verify `/footer` toggle state

The `/footer off` slash command sets `display.runtime_footer.enabled: false` globally. Check:

```bash
python -c "
from pathlib import Path
import yaml
cfg = yaml.safe_load(Path.home().joinpath('.hermes/config.yaml').read_text())
print('Global footer enabled:', cfg.get('display', {}).get('runtime_footer', {}).get('enabled'))
"
```

Re-enable with `/footer on` if it was toggled off.

## Key source files

| File | Role |
|------|------|
| `gateway/runtime_footer.py` | `build_footer_line()`, `resolve_footer_config()`, `format_runtime_footer()` |
| `gateway/run.py` `_respond_final()` | Footer assembly and appending (lines ~6502-6563) |
| `gateway/run.py` `_try_embed_stream_footer_in_place()` | Footer embed for streamed messages (line ~10300) |
| `gateway/platforms/feishu.py` | Feishu card footer (<note> element) |
| `gateway/platforms/telegram.py` | Telegram message editing & length limits |
| `~/.hermes/config.yaml` | Footer configuration |

## Common pitfalls

- **`fetch_account_usage` failure** is caught and sets `account_usage=None`, so it never crashes the footer. But the `usage` field silently disappears from the footer if the fetch fails.
- **The try/except in `_respond_final`** (line 6503-6560) catches ALL exceptions and sets `_footer_line = ""`. If ANYTHING in that block throws, no footer appears.
- **Global `enabled: false`** does NOT override per-platform `enabled: true` in config resolution, but the `/footer` toggle changes the global setting at runtime.
- **Test with `account_usage=None`** — the footer should still render with all other fields. If only `usage` and `tokens` are in the fields list and `account_usage` is None, the footer would be empty.
