---
name: hermes-footer
description: "Configure Hermes runtime footer — Feishu (in-card interactive note) and/or Telegram (plain-text with divider). Dispatch by channel."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [hermes, feishu, telegram, gateway, streaming, runtime-footer, config]
    related_skills: [hermes-agent]
---

# Hermes Runtime Footer — 调度入口

Use this skill when the user wants to **configure, verify, or repair** Hermes's runtime footer on a messaging platform.

This skill covers **two channels** in separate sections. **Only load the section that matches your target channel** — do not read both unless the user explicitly asked for both.

## Dispatch guide

Read the user's request to decide which section to follow:

| If the user says… | Go to section |
|---|---|
| 飞书 / Feishu / Lark — 配置或用不了 / 设置 footer / streaming | **Feishu section** |
| Telegram — 配置或用不了 / 设置 footer / 加分割线 | **Telegram section** |
| Discord — 配置或用不了 / 设置 footer / 加分割线 | **Discord section** |
| 同时配置多个平台 | Read relevant sections separately |

If the request is ambiguous (e.g. just "配置 footer"), ask which platform.

> **IMPORTANT disclaimer about token cost:** Hermes runtime footer is added by the gateway **after** the model finishes generating, using raw runtime metadata (model name, session, elapsed time, etc.). The footer text **never enters the LLM context window** — it is not part of the conversation history fed to the model on subsequent turns. Zero token waste.

> **Always load `hermes-agent` skill first** when making config changes, because Hermes config/CLI/gateway details evolve.

---

# Feishu Section — Interactive card footer

Configure Feishu/Lark gateway to stream replies by progressively editing the same interactive card, with runtime metadata embedded as a bottom `<note>` element in the card.

## Feishu config shape

```yaml
streaming:
  enabled: true
  transport: edit          # optional; default edit is fine

display:
  platforms:
    feishu:
      show_reasoning: false
      streaming: true
      runtime_footer:
        enabled: true
        separator: ' | '
        fields:
          - model
          - session
          - thinking
          - context
          - tokens
          - time
          - cwd
```

Field semantics (shared):

| Field | Example |
|-------|---------|
| `model` | `gpt-5.4` (vendor prefix stripped) |
| `session` | Session title, or first 8 chars of ID |
| `thinking` | Reasoning effort: `medium` / `off` |
| `context` | Context window usage: `42k / 200k (21%)` |
| `tokens` | Session cumulative: `in 1.2k out 567` |
| `usage` | API account usage: `5h 58% left ⏱4h 4m · Week 5% left ⏱1d 15h` |
| `time` | Wall-clock turn time: `12.3s` / `1m 5s` |
| `cwd` | Working dir with $HOME collapsed to `~` |

The user prefers **NOT** to show `Agent` field on Feishu.

## Apply Feishu config

Use a Python script to maintain correct YAML list formatting:

```bash
python - <<'PY'
from pathlib import Path
import yaml

p = Path.home() / '.hermes' / 'config.yaml'
cfg = yaml.safe_load(p.read_text(encoding='utf-8')) or {}

streaming = cfg.setdefault('streaming', {})
streaming['enabled'] = True
streaming.setdefault('transport', 'edit')

feishu = cfg.setdefault('display', {}).setdefault('platforms', {}).setdefault('feishu', {})
feishu['show_reasoning'] = False
feishu['streaming'] = True
feishu['runtime_footer'] = {
    'enabled': True,
    'separator': ' | ',
    'fields': ['model', 'session', 'thinking', 'context', 'tokens', 'usage'],
}

p.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding='utf-8')
print(p)
PY
hermes gateway restart

After restart, send a Feishu message and verify: (a) response updates in-place (streaming), (b) footer appears at the bottom of the same card as a `<note>` element.

## Verify Feishu source support

Config alone is not enough — the installed Hermes source must support Feishu interactive-card footers.

```bash
cd ~/.hermes/hermes-agent
grep -R "split_runtime_footer" -n gateway/runtime_footer.py gateway/platforms/feishu.py
grep -R "_build_interactive_card_payload\|feishu_card\|_try_embed_stream_footer_in_place" -n gateway/platforms/feishu.py gateway/run.py gateway/stream_consumer.py
```

Expected source touchpoints:

1. **`gateway/runtime_footer.py`** — `split_runtime_footer(text) -> (body, footer)` to separate card body from footer text.
2. **`gateway/platforms/feishu.py`** — imports `split_runtime_footer`, renders card body as `markdown` element and footer as bottom `note` element; both `send()` and `edit_message()` pass metadata.
3. **`gateway/run.py`** — builds footer line; when streaming already sent body, calls `_try_embed_stream_footer_in_place` to embed footer into existing card.
4. **`gateway/stream_consumer.py`** — passes adapter metadata through final edit path.

Run tests if available:

```bash
cd ~/.hermes/hermes-agent
python -m pytest -q tests/gateway/test_runtime_footer.py tests/gateway/test_feishu.py tests/gateway/test_update_streaming.py
```

## Repair Feishu after Hermes update

If `hermes update`, git pull, or plugin refactor removes footer behavior:

1. Check what changed:
   ```bash
   cd ~/.hermes/hermes-agent
   git status --short
   git diff -- gateway/platforms/feishu.py gateway/runtime_footer.py gateway/run.py gateway/stream_consumer.py
   ```

2. Re-apply config (see **Apply Feishu config** above).

3. If config is correct but Feishu sends a separate footer message or no footer, repair the source touchpoints listed in **Verify Feishu source support**.

4. Restart gateway:
   ```bash
   hermes gateway restart
   # or if wedged:
   systemctl --user restart hermes-gateway
   ```

5. Test with a real Feishu prompt and verify:
   - streamed content edits the same card
   - footer is embedded at the bottom of the same card as `<note>`
   - footer does NOT include `Agent` unless requested
   - no second trailing footer-only message appears

## Feishu local caveat

On this user's machine (as of 2026-05-07), Feishu footer-in-card is implemented as **local modifications** in `~/.hermes/hermes-agent` touching:
- `gateway/platforms/feishu.py`
- `gateway/runtime_footer.py`
- `gateway/run.py`
- `gateway/stream_consumer.py`

A future `hermes update` or upstream refactor can overwrite these if not committed upstream.

---

# Telegram Section — Plain-text footer

Configure Telegram to append a compact runtime-metadata footer at the end of each response, with an optional visual divider line.

## Telegram config shape

```yaml
display:
  platforms:
    telegram:
      streaming: true
      runtime_footer:
        enabled: true
        separator: ' | '
        prefix: "────────"     # 8-char horizontal rule as visual divider
        fields:
          - model
          - session
          - thinking
          - context
          - tokens
          - time
          - cwd
```

Key differences from Feishu:
- **`prefix: "────────"`** — a plain-text divider line before the footer fields. Set to empty string to disable.
- **No `show_reasoning: false`** — Telegram keeps `show_reasoning: true` (user preference).
- **No `streaming` top-level requirement** — the footer works with or without streaming, but streaming is recommended.

## Footer render example

When enabled, the Telegram message looks like:

```
[正文回复内容…]

────────
Model: gpt-5.4 | Session: abc12345 | Thinking: medium | Context: 42k / 200k (21%) | Tokens: in 1.2k out 567 | Usage: 5h 58% left ⏱4h 4m · Week 5% left ⏱1d 15h
```

The `prefix` is rendered as a separate line before the footer fields. The footer is appended by the gateway post-processing, not by the LLM — see the token disclaimer at the top of this skill.

## Apply Telegram config

```bash
python - <<'PY'
from pathlib import Path
import yaml

p = Path.home() / '.hermes' / 'config.yaml'
cfg = yaml.safe_load(p.read_text(encoding='utf-8')) or {}

telegram = cfg.setdefault('display', {}).setdefault('platforms', {}).setdefault('telegram', {})
telegram['streaming'] = True
telegram['runtime_footer'] = {
    'enabled': True,
    'separator': ' | ',
    'prefix': '────────',
    'fields': ['model', 'session', 'thinking', 'context', 'tokens', 'usage'],
}

p.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding='utf-8')
print(p)
PY
hermes gateway restart

## Verify Telegram footer

After restart, send a message to Hermes on Telegram and check:
- The response ends with the footer line
- The `────────` separator appears above the fields
- No footer appears on platforms that don't have it enabled

If no footer shows, check:
1. The Telegram platform override is correct: `display.platforms.telegram.runtime_footer.enabled: true`
2. The global `display.runtime_footer.enabled` is NOT overriding it to `false`
3. Toggle with `/footer on` command to confirm runtime toggle works

## Telegram layout semantics — why the footer may not look “attached”

If the user asks why the footer is **not directly glued to the last line of the reply body**, inspect both config and gateway code before assuming Telegram rendering is at fault.

Current Hermes behavior:

- `gateway/run.py` appends the footer with **two newlines**: `response + "\n\n" + footer_line`
- `gateway/runtime_footer.py` renders `prefix` (for example `────────`) on its **own line** above the footer fields
- therefore the normal Telegram layout is intentionally:

```text
[body]

────────
Model: ... | Session: ...
```

So even when the footer is in the **same Telegram message**, it is still separated from the body by a blank line plus the divider line.

Streaming nuance:
- for streamed replies, Hermes first sends the body, then tries to edit the final streamed message in place via `_try_embed_stream_footer_in_place(...)`
- if that edit fails, or if the combined body+footer would exceed Telegram's `4096` UTF-16 limit, Hermes falls back to sending the footer as a **separate tiny trailing message**

Key code touchpoints for this diagnosis:
- `gateway/run.py` — footer assembly and streamed fallback behavior
- `gateway/runtime_footer.py` — `prefix`/separator rendering
- `gateway/platforms/telegram.py` — edit behavior and message-length limits

If the user wants a tighter look, there are three distinct options:
1. Keep current behavior — blank line + divider + footer
2. Keep same-message footer but make it visually tighter by changing the join from `\n\n` to `\n`
3. Remove the divider by setting Telegram `runtime_footer.prefix` to empty string

## Repair Telegram after Hermes update

Same process as Feishu but focus on `runtime_footer.py`:

```bash
cd ~/.hermes/hermes-agent
git diff -- gateway/runtime_footer.py gateway/run.py
```

If `build_footer_line` or `resolve_footer_config` changed, re-check the config file and restart.

## Switching off the footer

To temporarily disable without removing config:

```bash
hermes config set display.platforms.telegram.runtime_footer.enabled false
```

Or use the `/footer off` slash command (affects global, not per-platform).

---

# Discord Section — Plain-text footer

Configure Discord to append a compact runtime-metadata footer at the end of each response, with an optional visual divider line.

## Discord config shape

```yaml
display:
  platforms:
    discord:
      show_reasoning: true
      streaming: true
      runtime_footer:
        enabled: true
        separator: ' | '
        prefix: "────────"
        fields:
          - model
          - session
          - thinking
          - context
          - tokens
          - usage
```

Key characteristics shared with Telegram:
- **`prefix: "────────"`** — a plain-text divider line before the footer fields. Set to empty string to disable.
- **`show_reasoning`** defaults to `true` (user preference — unlike Feishu which sets it to `false`).
- Footer works with or without streaming.

## Discord footer behavior

Unlike Feishu (card-based in-place edit) and Telegram (edit-message-in-place), Discord's footer delivery depends on the response mode:

- **Non-streaming mode**: The footer is joined to the response body with `\n\n` and sent as part of the same message.
- **Streaming mode**: `_try_embed_stream_footer_in_place` (in `gateway/run.py`) currently only supports `Platform.FEISHU` and `Platform.TELEGRAM`. For Discord, the embedding check returns `False`, so the gateway falls back to sending the footer as a **separate trailing message** after the streamed body completes.

This means in streaming mode the Discord output looks like:

```
[主播回复内容...]

────────
Model: deepseek-v4-pro | Session: abc12345 | Thinking: high | ...
```

## Apply Discord config

```bash
python - <<'PY'
from pathlib import Path
import yaml

p = Path.home() / '.hermes' / 'config.yaml'
cfg = yaml.safe_load(p.read_text(encoding='utf-8')) or {}

discord = cfg.setdefault('display', {}).setdefault('platforms', {}).setdefault('discord', {})
discord['show_reasoning'] = True
discord['streaming'] = True
discord['runtime_footer'] = {
    'enabled': True,
    'separator': ' | ',
    'prefix': '────────',
    'fields': ['model', 'session', 'thinking', 'context', 'tokens', 'usage'],
}

p.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding='utf-8')
print(p)
PY
hermes gateway restart
```

## Verify Discord footer

After restart, send a message to Hermes on Discord and check:
- The response ends with the footer (non-streaming) or receives a separate footer message (streaming)
- The `────────` separator appears above the fields
- No footer appears on platforms that don't have it enabled

If no footer shows:
1. Confirm `display.platforms.discord.runtime_footer.enabled: true`
2. The global `display.runtime_footer.enabled` is NOT overriding it to `false`
3. Restart the gateway: `hermes gateway restart` (config changes require restart)

## Switching off the Discord footer

```bash
hermes config set display.platforms.discord.runtime_footer.enabled false
hermes gateway restart
```

---

# References

- `references/diagnose-missing-footer.md` — 当用户报告 footer 消失时的系统诊断流程。检查配置解析、API 429 错误、streaming 与非 streaming 代码路径、`/footer` toggle 状态。

# Common pitfalls

- **Do not only set `display.streaming`** — gateway streaming uses the top-level `streaming` block, not `display.streaming` (which is CLI-only).
- **Do not assume platforms inherit each other's config** — each platform needs its own `display.platforms.<name>.runtime_footer` block.
- **Always restart the gateway** after config or code changes. Toggle via `hermes gateway restart`.
- **The `/footer` slash command** toggles `display.runtime_footer.enabled` globally; per-platform overrides still apply individually.
- **Telegram / Discord prefix** is a config-level string, not a code change. Adjust `prefix` in YAML to change the divider.
- **Discord streaming footer** is sent as a separate trailing message; this is by design because `_try_embed_stream_footer_in_place` in `gateway/run.py` only handles Feishu and Telegram. To change this behavior, add `Platform.DISCORD` to the guard condition in `gateway/run.py` (line ~10322).
