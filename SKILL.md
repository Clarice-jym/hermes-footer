---
name: hermes-footer
description: "Configure Hermes runtime footer — detect version, fix missing footers, migrate config, or restore rich fields."
version: 2.0.3
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [hermes, feishu, telegram, discord, gateway, streaming, runtime-footer, config]
    related_skills: [hermes-agent]
---

# Hermes Runtime Footer — 调度入口

Use this skill when the user wants to **configure, verify, or repair** Hermes's runtime footer on a messaging platform.

The current Hermes runtime footer on this machine is the **rich-field system**.

## Current reality

The live `gateway/runtime_footer.py` supports rich fields via `_RUNTIME_FOOTER_LABELS`, including:

- `model`
- `session`
- `thinking`
- `context`
- `tokens`
- `usage`
- `time`
- `cost`
- `cwd`

It also supports:

- configurable `separator` from `config.yaml`
- configurable `prefix` (for example `────────`)
- per-platform field lists under `display.platforms.<platform>.runtime_footer`

For this user's setup, the preferred separator is ` | `.

The current preferred visible order on Feishu / Telegram / Discord is:

- `model`
- `cwd`
- `thinking`
- `context`
- `tokens`
- `cost`
- `usage`

That means the second visible footer slot should now be `cwd`, not `session`.

Typical rendered examples:

- Feishu: `Model: free | CWD: ~/.hermes | Thinking: medium | Context: 12.3k / 200.0k (6%) | Tokens: in 1.5k out 320 | Cost: $0.00`
- Telegram / Discord:
  - `────────`
  - `Model: free | CWD: ~/.hermes | Thinking: medium | Context: 12.3k / 200.0k (6%) | Tokens: in 1.5k out 320 | Cost: $0.00`

## First step: verify the live code before changing docs or config

```bash
cd ~/.hermes/hermes-agent
python3 - <<'PY'
from pathlib import Path
p = Path('gateway/runtime_footer.py')
text = p.read_text(encoding='utf-8')
print('_RUNTIME_FOOTER_LABELS' in text)
print('"cwd": "CWD"' in text)
print('"cost": "Cost"' in text)
PY
```

If that check is true for these rich-field markers, treat the system as rich-footer and edit config directly.

## Dispatch guide

| User request | Recommended action |
|---|---|
| "Footer disappeared" | Check config resolution, gateway logs, and whether the response path was successful |
| "Add/remove/reorder a field" | Edit per-platform `runtime_footer.fields`, restart gateway, verify rendering |
| "Change separator/prefix" | Edit `separator` / `prefix` in config, restart gateway, verify |
| "Show cwd instead of session" | Verify each target platform uses `fields: [model, cwd, thinking, context, tokens, cost, usage]`, keep `cwd` in the second visible slot, and update the skill templates/examples so all three platforms stay aligned |
| "Add custom field like cost" | Follow the code pattern in references if the live code lacks it; otherwise just add it to config |

## Historical note

Some older skill text referred to a short-lived simplified rewrite that only rendered `model`, `context_pct`, and `cwd`. That is **not** the active footer implementation in this environment. Keep those notes only as historical debugging context, not as the primary operating model.

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

- **Field list mismatches still matter** — if the footer shows the wrong value (for example `Session` when the user wants `CWD`), check `display.platforms.<platform>.runtime_footer.fields` first.
- **For this user's setup, Feishu / Telegram / Discord should stay in sync** — when changing one platform's runtime footer field order, update the other two and refresh the skill templates in the same pass.
- **The try/except in `_respond_final`** catches ALL exceptions and sets `_footer_line = ""`. Any error in footer building = no footer, no error message to user. Always check gateway logs for `runtime_footer build failed` before assuming config is wrong.
- **Do not port old footer snippets without re-checking variable scope** — after Hermes updates, `gateway/run.py` structure may change. In particular, the final-response footer block may not have access to a bare `agent` object; pass needed values through `agent_result` instead. See `references/restore-rich-fields.md` pitfalls.
- **Streaming replies are a separate path** — if `agent_result.already_sent` is true, attach footer by editing `stream_message_id` in place when possible, then fall back to a trailing footer message.
- **Per-platform `enabled: true` overrides** global `enabled: false` — the `/footer off` command changes the global, not per-platform.
- **Gateway restart is mandatory** after any config or code change.

---

# References

- `references/diagnose-missing-footer.md` — Full diagnostic flow for missing footers (version-agnostic).
- `references/restore-rich-fields.md` — Historical recovery notes for older stripped-down footer revisions.
- `references/add-custom-footer-field.md` — Rich-footer codepath notes for adding or tracing fields like `cost`.

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
- **Per-platform field lists win the user-visible output** — if the footer text is structurally wrong, inspect the exact `fields` order on that platform before touching code.
