# Adding a custom footer field — session trace (2026-05-11)

> **Historical note:** this reference was originally written while tracing how a custom `cost` field was added. The current live environment already uses the rich `_RUNTIME_FOOTER_LABELS` footer implementation, so the code paths below are directly relevant when that implementation is still present.
> If you inspect an older checkout that really only has the 3-field footer, see `references/restore-rich-fields.md` for the historical restoration notes.

This file captures the exact code paths and line numbers discovered while adding a `cost` field to the runtime footer for `Cost: Today $0.96`.

## Files touched

| File | Purpose |
|------|---------|
| `~/.hermes/hermes-agent/gateway/runtime_footer.py` | Field label registry + renderer |
| `~/.hermes/hermes-agent/gateway/run.py` | Data computation & parameter passing |
| `~/.hermes/config.yaml` | Field list for each platform |

## `runtime_footer.py` key locations

- **Line 43**: `_DEFAULT_FIELDS` — built-in default field list
- **Lines 46-58**: `_RUNTIME_FOOTER_LABELS` — add new field labels here
- **Line 60**: `_RUNTIME_FOOTER_PREFIXES` — auto-generated from labels, no manual update needed
- **Lines 289-367**: `format_runtime_footer()` — add parameter + rendering branch
- **Lines 358**: `# Unknown field names are silently ignored.` — the `else` fallthrough
- **Lines 408-452**: `build_footer_line()` — add parameter pass-through

## `run.py` key locations

- **Lines ~6502-6554**: Footer building block — where `build_footer_line` is called and `agent_result` fields are accessed
- **Lines ~12300-12307**: `_run_agent()` docstring — describes what `agent_result` contains
- **Lines ~6550-6551**: `input_tokens` and `output_tokens` are from `agent_result` (session-level accumulated totals)

## `agent_result` keys used for cost

From `run_agent.py` ~L13890-13904:

```python
"estimated_cost_usd": self.session_estimated_cost_usd,   # float
"cost_status": self.session_cost_status,                   # "estimated" / "included" / "unknown"
"cost_source": self.session_cost_source,                   # e.g. "official_docs_snapshot"
```

## Example: `cost` field implementation

### `runtime_footer.py`

Add to `_RUNTIME_FOOTER_LABELS`:
```python
"cost": "Cost",
```

In `format_runtime_footer()`, add after the `cwd` branch (~L355):
```python
elif field == "cost":
    if cost_str:
        parts.append(f"{_RUNTIME_FOOTER_LABELS['cost']}: {cost_str}")
```

`build_footer_line()` gets the same `cost_str` param and passes it through.

### `run.py`

Before the `_bfl(...)` call (~L6538):
```python
_footer_cost_str = ""
_cost_usd = agent_result.get("estimated_cost_usd")
_cost_status = agent_result.get("cost_status")
if _cost_usd is not None and _cost_usd > 0:
    prefix = "~" if _cost_status == "estimated" else ""
    _footer_cost_str = f"Today {prefix}${_cost_usd:.2f}"
```

Then pass `cost_str=_footer_cost_str` to `_bfl(...)`.

### `config.yaml`

Add `cost` to the `fields` list for each platform:
```yaml
fields:
  - model
  - cwd
  - cost
  - ...
```

## Testing

Send a message on each platform and verify the footer shows `Cost: Today $0.96` (or `Cost: Today ~$0.96` for estimated pricing). If it doesn't appear:
1. Check `hermes gateway restart` was done
2. Check `_footer_cost_str` has a non-empty value (log level DEBUG to see)
3. Check the field name matches exactly between config YAML and the `elif field == "cost":` branch
