---
name: hermes-footer
description: "Configure Hermes runtime footer — detect version, fix missing footers, migrate config, or restore rich fields."
version: 2.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [hermes, feishu, telegram, discord, gateway, streaming, runtime-footer, config]
    related_skills: [hermes-agent]
---

# Hermes Runtime Footer — 调度入口

Use this skill when the user wants to **configure, verify, or repair** Hermes's runtime footer on a messaging platform.

The footer system has **two possible versions** depending on whether `hermes update` pulled the simplified rewrite:

| Aspect | Old system (pre-May 2026) | New system (post-rewrite) |
|--------|--------------------------|---------------------------|
| Supported fields | `model`, `session`, `thinking`, `context`, `tokens`, `usage`, `time`, `cwd`, `cost` (custom) | `model`, `context_pct`, `cwd` only |
| Custom separator | Read from `config.yaml` `separator` key | Hardcoded ` · ` (middle dot) |
| Prefix/divider | `prefix` key in config (e.g. `────────`) | Not supported |
| Custom fields | Code pattern in `runtime_footer.py` | Not supported without code extension |
| Per-platform config | Full per-platform with separator/prefix/field list | Same config shape, but `separator`/`prefix` ignored, unknown fields silently dropped |

> **IMPORTANT**: Unknown field names in `fields` are **silently ignored** by the new `format_runtime_footer()`. If footers disappeared after an update, the config still looks correct but references fields that no longer exist in code.

## First step: detect which version

```bash
cd ~/.hermes/hermes-agent
head -30 gateway/runtime_footer.py
```

If you see `_DEFAULT_FIELDS = ("model", "context_pct", "cwd")` and a simple `format_runtime_footer()` with only 3 field branches → **new system**.
If you see `_RUNTIME_FOOTER_LABELS` dict with many entries → **old system**.

## Dispatch guide

Once you know the version, decide the approach:

| User request | Old system | New system |
|---|---|---|
| "Footer disappeared after update" | Check config & restart | Config references now-gone fields → see **Migration** below |
| "Add/remove a field" | Edit config → restart | Only `model`, `context_pct`, `cwd` available |
| "Add custom field like `cost`" | Follow code pattern in references | Must **extend code** (see **Restoring rich footer** below) |
| "Change separator/prefix" | Edit config → restart | Not supported in new system |

---

# Migration: New system — making footers visible again

## Problem

After `hermes update`, the user's config still has:
```yaml
runtime_footer:
  enabled: true
  fields: [model, session, thinking, context, tokens, usage]
```

But the new code only supports `model`, `context_pct`, `cwd`. Fields like `session`, `thinking`, `tokens`, `usage` are silently ignored. Result: only `model` prints, or if that's also misconfigured — empty footer.

## Option A: Adapt to new system (minimal, no code changes)

Update each platform's config to use only supported fields:

```bash
python3 - <<'PY'
from pathlib import Path
import yaml

p = Path.home() / '.hermes' / 'config.yaml'
cfg = yaml.safe_load(p.read_text(encoding='utf-8')) or {}

new_fields = ['model', 'context_pct']  # cwd optional

for plat in ['feishu', 'telegram', 'discord']:
    plat_cfg = cfg.get('display', {}).get('platforms', {}).get(plat, {})
    if 'runtime_footer' in plat_cfg:
        plat_cfg['runtime_footer']['fields'] = new_fields
        # separator and prefix are now ignored by new code; keep or remove
        plat_cfg['runtime_footer'].pop('separator', None)
        plat_cfg['runtime_footer'].pop('prefix', None)

p.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding='utf-8')
print("Updated:", p)
PY
hermes gateway restart
```

Verify: send a message on each platform. Footer should show something like `gpt-5.4 · 12%`.

## Option B: Restore rich footer (extend code)

This re-adds the old field support and custom separator/prefix to the new simplified codebase.

### Files to modify

| File | Change |
|------|--------|
| `gateway/runtime_footer.py` | Add `session`, `thinking`, `tokens`, `usage`, `time` field branches; restore configurable `_SEP` and prefix support |
| `gateway/run.py` | Pass `session_id`, `input_tokens`, `output_tokens`, `elapsed_seconds`, `reasoning_config`, `account_usage` to `build_footer_line()` |

The `agent_result` dict (available in `_respond_final` around `gateway/run.py` L7635) contains:
- `model`, `session_id`, `last_prompt_tokens`, `context_length`
- `input_tokens`, `output_tokens` (session cumulative)
- `estimated_cost_usd`, `cost_status` (for custom `cost` field)
- `reasoning_effort` (from session config)
- `account_usage` (from usage tracking)

### Reference file for restoration

See `references/restore-rich-fields.md` for the full code changeset including:
- Exact field rendering branches for `format_runtime_footer()`
- How to wire separator and prefix from config into the new code
- How to pass `cost_str` for the `cost` field
- Pitfalls around the try/except that catches all footer errors

---

# Diagnostic process (version-agnostic)

## Step 1: Verify config resolution

```bash
python3 -c '
from pathlib import Path
import yaml
from gateway.runtime_footer import resolve_footer_config

cfg = yaml.safe_load(Path.home().joinpath(".hermes/config.yaml").read_text())
for p in ["telegram", "feishu", "discord"]:
    r = resolve_footer_config(cfg, p)
    print(f"{p}: enabled={r[\"enabled\"]}, fields={r[\"fields\"]}")
'
```

If `enabled=True` with the right fields → config is fine, issue is in code.

## Step 2: Check gateway logs for footer activity

```bash
journalctl --user -u hermes-gateway --since "30 min ago" --no-pager | grep -i -E "footer built|runtime_footer|stream footer" | tail -20
```

No "footer built" lines → the try/except block in `_respond_final` caught an error, or the footer function returned empty.

## Step 3: Test standalone

```python
from gateway.runtime_footer import build_footer_line
from hermes_cli.config import read_raw_config

cfg = read_raw_config()
line = build_footer_line(
    user_config=cfg,
    platform_key="telegram",
    model="deepseek-v4-flash",
    context_tokens=12345,
    context_length=200000,
    cwd="/home/momo",
)
print(repr(line))
```

If this returns `""`, check whether `cfg["display"]["runtime_footer"]["enabled"]` is overriding per-platform `enabled`.

## Step 4: Check `/footer` toggle

```bash
hermes config get display.runtime_footer.enabled
```

If `false`, run `/footer on` in any platform.

## Key pitfalls

- **New code silently ignores unknown fields** — the most common cause of "footer disappeared" after update. The config looks fine, but `session`, `thinking`, `tokens`, `usage` don't exist in new code.
- **The try/except in `_respond_final`** catches ALL exceptions and sets `_footer_line = ""`. Any error in footer building = no footer, no error message to user.
- **Per-platform `enabled: true` overrides** global `enabled: false` — the `/footer off` command changes the global, not per-platform.
- **Gateway restart is mandatory** after any config or code change.

---

# References

- `references/diagnose-missing-footer.md` — Full diagnostic flow for missing footers (version-agnostic).
- `references/restore-rich-fields.md` — Code changeset to restore the old multi-field footer system on the new simplified codebase.
- `references/add-custom-footer-field.md` — Legacy: how custom fields were added in old system (kept for migration reference).

# Maintenance

This skill is version-controlled at [github.com/Clarice-jym/hermes-footer](https://github.com/Clarice-jym/hermes-footer).
Update procedure:

1. Edit the skill files locally (`~/.hermes/skills/autonomous-ai-agents/hermes-footer/`)
2. Clone the repo if needed: `gh repo clone Clarice-jym/hermes-footer /tmp/hermes-footer`
3. Copy updated files over: `cp -r ~/.hermes/skills/.../hermes-footer/* /tmp/hermes-footer/`
4. Commit and push: `cd /tmp/hermes-footer && git add -A && git commit -m "..." && git push`

**Important**: code changes (to `gateway/runtime_footer.py`, `gateway/run.py`, `config.yaml`) are **documented in the skill reference files** (`restore-rich-fields.md`, `diagnose-missing-footer.md`) but are **NOT committed separately** to any repo. The skill IS the authoritative fix documentation. The user's Hermes instance has the local code patches; a future `hermes update` may overwrite them, and the skill provides the recipe to re-apply.

# Common pitfalls

- **Do not only set `display.streaming`** — gateway streaming uses the top-level `streaming` block, not `display.streaming`.
- **Always restart the gateway** after config or code changes: `hermes gateway restart`.
- **The `/footer` slash command** toggles `display.runtime_footer.enabled` globally; per-platform overrides still apply individually.
- **New code unknown fields are silent** — if footers vanished, check the field names against what `format_runtime_footer()` actually renders.
