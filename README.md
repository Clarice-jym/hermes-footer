# hermes-footer

A Hermes Agent skill for configuring **runtime footer** on **Feishu (Lark)** and **Telegram** channels.

## Features

- **Feishu** — Footer embedded as a `<note>` element inside the interactive card, enabled through gateway streaming
- **Telegram** — Footer appended as plain text with an optional visual divider (`────────`)
- **Dispatch mechanism** — The SKILL.md dispatch table routes the agent to the correct channel section, preventing unnecessary context
- **Zero token cost** — Footer is added by the gateway after the model finishes; never enters the LLM context window

## What's inside

```
hermes-footer/
├── SKILL.md                         # Main skill — dispatch + Feishu section + Telegram section
├── README.md
├── templates/
│   ├── feishu-config.yaml           # Feishu config snippet
│   └── telegram-config.yaml         # Telegram config snippet (with prefix divider)
└── scripts/
    ├── check_footer_feishu.py       # Diagnose Feishu footer config & source support
    └── check_footer_telegram.py     # Diagnose Telegram footer config & source support
```

## Usage

Run the check scripts to quickly diagnose issues:

```bash
python ~/.hermes/skills/autonomous-ai-agents/hermes-footer/scripts/check_footer_feishu.py
python ~/.hermes/skills/autonomous-ai-agents/hermes-footer/scripts/check_footer_telegram.py
```

Or load the skill and let Hermes walk you through the setup.
