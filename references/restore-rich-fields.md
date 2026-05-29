# Restore Rich Footer Fields (post-May 2026 rewrite)

This reference documents how to restore the old multi-field footer system after the Hermes rewrite that simplified `runtime_footer.py` to only 3 fields (`model`, `context_pct`, `cwd`).

## Root cause

The update (commit range from ~May 12, 2026) rewrote `gateway/runtime_footer.py`:

```
Old: _RUNTIME_FOOTER_LABELS dict + format_runtime_footer() with 10 field branches
New: format_runtime_footer() with 3 field branches, hardcoded " · " separator
```

The `build_footer_line()` signature was also simplified:
```
Old: model, provider, session_id, reasoning_config, context_tokens, context_length,
     input_tokens, output_tokens, account_usage, elapsed_seconds, cwd, cost_str, ...
New: model, context_tokens, context_length, cwd
```

## Config was NOT the problem

If the user's config has:
```yaml
fields: [model, session, thinking, context, tokens, usage]
```

This looks correct but `session`, `thinking`, `tokens`, `usage` are **unknown field names** in the new code and are silently dropped by the `else` branch (which does nothing). Only `model` survives, but `context` was also renamed to `context_pct`.

## Full restoration: `gateway/runtime_footer.py`

Replace the file content with an extended version that supports the old field set while keeping the new code's structure. The key changes:

### 1. Configurable separator

```python
# Near the top, replace hardcoded _SEP:
# _SEP = " · "  # old
_SEP = " · "    # default, can be overridden

def resolve_footer_config(user_config, platform_key=None) -> dict:
    """Also extract separator and prefix from config."""
    resolved = {"enabled": False, "fields": list(_DEFAULT_FIELDS), "separator": " · ", "prefix": ""}
    # ... existing merge logic ...
    
    # Add separator extraction:
    if isinstance(global_cfg, dict) and isinstance(global_cfg.get("separator"), str):
        resolved["separator"] = global_cfg["separator"]
    if platform_key:
        plat_cfg = platforms.get(platform_key, {})
        plat_footer = plat_cfg.get("runtime_footer", {})
        if isinstance(plat_footer, dict):
            if isinstance(plat_footer.get("separator"), str):
                resolved["separator"] = plat_footer["separator"]
            if isinstance(plat_footer.get("prefix"), str):
                resolved["prefix"] = plat_footer["prefix"]
    return resolved
```

### 2. `format_runtime_footer()` with old field branches

```python
def format_runtime_footer(
    *,
    model: Optional[str],
    context_tokens: int,
    context_length: Optional[int],
    session_id: Optional[str] = None,
    reasoning_effort: Optional[str] = None,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    account_usage: Optional[dict] = None,
    elapsed_seconds: Optional[float] = None,
    cost_str: Optional[str] = None,
    cwd: Optional[str] = None,
    fields: Iterable[str] = _DEFAULT_FIELDS,
    separator: str = " · ",
    prefix: str = "",
) -> str:
    parts: list[str] = []
    for field in fields:
        if field == "model":
            m = _model_short(model)
            if m: parts.append(m)
        elif field == "session":
            if session_id:
                parts.append(session_id[:20])  # truncate long IDs
        elif field == "thinking":
            if reasoning_effort:
                parts.append(reasoning_effort)
        elif field == "context" or field == "context_pct":
            if context_length and context_length > 0 and context_tokens >= 0:
                pct = max(0, min(100, round((context_tokens / context_length) * 100)))
                # Old style: "60.8k / 1.0M (6%)"
                ctx_str = _format_tokens(context_tokens)
                ctx_len_str = _format_tokens(context_length)
                parts.append(f"{ctx_str} / {ctx_len_str} ({pct}%)")
        elif field == "tokens":
            if input_tokens is not None or output_tokens is not None:
                tokens_parts = []
                if input_tokens is not None:
                    tokens_parts.append(f"in {_format_tokens(input_tokens)}")
                if output_tokens is not None:
                    tokens_parts.append(f"out {_format_tokens(output_tokens)}")
                parts.append(" ".join(tokens_parts))
        elif field == "usage":
            if account_usage:
                parts.append(_format_account_usage(account_usage))
        elif field == "time":
            if elapsed_seconds is not None:
                parts.append(_format_elapsed(elapsed_seconds))
        elif field == "cost":
            if cost_str:
                parts.append(f"Cost: {cost_str}")
        elif field == "cwd":
            rel = _home_relative_cwd(cwd or "")
            if rel: parts.append(rel)
        # Unknown fields silently ignored

    if not parts:
        return ""
    line = separator.join(parts)
    if prefix:
        line = f"{prefix}\n{line}"
    return line


def _format_tokens(n: int) -> str:
    """Format token count: 1234 -> '1.2k', 1234567 -> '1.2M'."""
    if n < 1000:
        return str(n)
    elif n < 1000000:
        return f"{n/1000:.1f}k"
    else:
        return f"{n/1000000:.1f}M"


def _format_elapsed(seconds: float) -> str:
    """Format elapsed time: 12.3 -> '12.3s', 65 -> '1m 5s'."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    if minutes < 60:
        return f"{minutes}m {secs}s"
    hours = minutes // 60
    minutes = minutes % 60
    return f"{hours}h {minutes}m"



def _format_relative_reset_hours(dt: Optional[datetime]) -> str:
    """Return reset time for the short usage footer, e.g. ``4h`` or ``5d 8h``."""
    if not dt:
        return ""
    total_seconds = int((dt - datetime.now(timezone.utc)).total_seconds())
    if total_seconds <= 0:
        return "now"
    hours = max(1, round(total_seconds / 3600))
    if hours >= 24:
        days, rem_hours = divmod(hours, 24)
        return f"{days}d {rem_hours}h" if rem_hours else f"{days}d"
    return f"{hours}h"


def _usage_label_short(label: Optional[str]) -> str:
    raw = str(label or "").strip()
    normalized = raw.casefold()
    mapping = {
        "session": "5h",
        "current session": "5h",
        "five hour": "5h",
        "five-hour": "5h",
        "5h": "5h",
        "weekly": "Week",
        "current week": "Week",
        "week": "Week",
        "7d": "Week",
    }
    return mapping.get(normalized, raw)


def _format_account_usage(account_usage: Any, *, separator: str = _DEFAULT_SEP) -> str:
    """Render account-usage windows in the user's short C format.

    Example: ``73%/4h, Week 91%/5d 8h``. The first short/session window omits
    its label; longer-period windows keep a compact label such as ``Week``.
    ``separator`` is accepted for API compatibility but intentionally not used
    inside this field so the footer-level separator remains visually distinct.
    """
    if not account_usage:
        return ""
    windows = getattr(account_usage, "windows", None) or ()
    parts: list[str] = []
    for window in windows:
        used_percent = getattr(window, "used_percent", None)
        if used_percent is None:
            continue
        label = _usage_label_short(getattr(window, "label", None))
        if not label:
            continue
        try:
            remaining = max(0, round(100 - float(used_percent)))
        except (TypeError, ValueError):
            continue

        reset_text = _format_relative_reset_hours(getattr(window, "reset_at", None))
        quota = f"{remaining}%/{reset_text}" if reset_text else f"{remaining}%"
        if label == "5h":
            parts.append(quota)
        else:
            parts.append(f"{label} {quota}")
    return ", ".join(parts)

```

### 3. `build_footer_line()` — pass through all params

```python
def build_footer_line(
    *,
    user_config: dict[str, Any] | None,
    platform_key: str | None,
    model: Optional[str],
    context_tokens: int,
    context_length: Optional[int],
    session_id: Optional[str] = None,
    reasoning_effort: Optional[str] = None,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    account_usage: Optional[dict] = None,
    elapsed_seconds: Optional[float] = None,
    cost_str: Optional[str] = None,
    cwd: Optional[str] = None,
) -> str:
    cfg = resolve_footer_config(user_config, platform_key)
    if not cfg.get("enabled"):
        return ""
    return format_runtime_footer(
        model=model,
        context_tokens=context_tokens,
        context_length=context_length,
        session_id=session_id,
        reasoning_effort=reasoning_effort,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        account_usage=account_usage,
        elapsed_seconds=elapsed_seconds,
        cost_str=cost_str,
        cwd=cwd,
        fields=cfg.get("fields") or _DEFAULT_FIELDS,
        separator=cfg.get("separator", " · "),
        prefix=cfg.get("prefix", ""),
    )
```

## Full restoration: `gateway/run.py`

Find the `_respond_final` block around L7635 where `build_footer_line` is called. Change the call to pass the old params:

```python
from gateway.runtime_footer import build_footer_line as _bfl

# Compute cost if available
_footer_cost_str = ""
_cost_usd = agent_result.get("estimated_cost_usd")
_cost_status = agent_result.get("cost_status")
if _cost_usd is not None and _cost_usd > 0:
    _prefix = "~" if _cost_status == "estimated" else ""
    _footer_cost_str = f"Today {_prefix}${_cost_usd:.2f}"

_footer_line = _bfl(
    user_config=_load_gateway_config(),
    platform_key=_platform_config_key(source.platform),
    model=agent_result.get("model"),
    context_tokens=agent_result.get("last_prompt_tokens", 0) or 0,
    context_length=agent_result.get("context_length") or None,
    session_id=agent_result.get("session_id"),
    reasoning_effort=agent_result.get("reasoning_effort"),
    input_tokens=agent_result.get("input_tokens"),
    output_tokens=agent_result.get("output_tokens"),
    account_usage=agent_result.get("account_usage"),
    elapsed_seconds=agent_result.get("elapsed_seconds"),
    cost_str=_footer_cost_str,
    cwd=os.environ.get("TERMINAL_CWD", ""),
)
```

## Data source: `agent_result` keys

From `run_agent.py`'s `run_conversation()` return:

| Key | Source | Type |
|---|---|---|
| `model` | Resolved model name | `str` |
| `session_id` | Current session ID | `str` |
| `last_prompt_tokens` | Token count for the last prompt | `int` |
| `context_length` | Max context window | `int` |
| `input_tokens` | Session cumulative input tokens | `int` |
| `output_tokens` | Session cumulative output tokens | `int` |
| `estimated_cost_usd` | Session accumulated cost | `float` |
| `cost_status` | `"estimated"`, `"included"`, or `"unknown"` | `str` |
| `reasoning_effort` | `"high"`, `"medium"`, `"low"`, or `None` | `str` |
| `account_usage` | API usage dict from provider | `dict` or `None` |
| `already_sent` | Whether body was streamed already | `bool` |

Note: `account_usage` and `elapsed_seconds` may not be in `agent_result` directly — they might need to be tracked in the `GatewayRunner` instance. Check `self._last_account_usage` or similar fields in the gateway runner.

## Pitfalls

- **The try/except in `_respond_final`** catches ALL exceptions and sets `_footer_line = ""`. After code changes, always check `journalctl --user -u hermes-gateway` for debug logs (`runtime_footer build failed: ...`).
- **`agent_result` keys vary by provider** — some providers don't return `account_usage` or `estimated_cost_usd`. Guard with `.get()`.
- **Footer `usage` is fetched at footer-build time**, not returned in `agent_result`: `gateway/run.py` calls `agent.account_usage.fetch_account_usage(provider, base_url=..., api_key=...)`, then passes the snapshot to `build_footer_line()`. Prefer `agent_result` runtime values, but fall back to `config.yaml` `model.provider` / `model.base_url` if they are missing. Log `footer usage fetch: provider=... windows=... available=...` so missing usage is diagnosable instead of silent.
- **Do not reference a bare `agent` from the final-response footer block**. The real AIAgent instance lives inside `_run_agent()`/`run_sync()` and is not in scope where `_footer_line` is built in `_handle_message_with_agent`. If you need provider/base_url/api_key/cost/reasoning/model values, return them in `agent_result` from `_run_agent()` first, then read them with `agent_result.get(...)`. A bare `agent` reference raises `NameError: name 'agent' is not defined`; the broad footer try/except then silently drops the whole footer.
- **Streaming replies need an `already_sent` path**. If `agent_result['already_sent']` is true, the body was already delivered by the stream consumer; append the footer by editing `agent_result['stream_message_id']` in place when available (preserving Feishu card metadata), and only fall back to a small trailing footer message if edit-in-place fails.
- **`fetch_account_usage()` catches provider/API failures and returns `None`**; add an INFO log in `agent/account_usage.py` while debugging (`account usage unavailable for provider=...`) so 401/429/network failures explain why `usage` is skipped.
- **`_load_gateway_config()`** may cache the config; changes to `config.yaml` require a gateway restart even if `runtime_footer.py` code is already updated.
- **The old `field == "context"` no longer exists** — it was renamed to `context_pct`. Support both names for backward compat with existing configs.
- **Token counts in `agent_result` are session cumulative**, not per-turn. For per-turn display, track previous values in the `GatewayRunner` instance.

## Verification

After applying changes and restarting the gateway:

1. Check the log: `journalctl --user -u hermes-gateway --since "1 min ago" | grep "footer built"`
2. Send a message on each platform
3. Verify: each platform shows footer with the configured fields and separator
