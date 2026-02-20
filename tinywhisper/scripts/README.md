# TinyWhisper — Prompt Scripts

The **Prompt Script** mode lets you control exactly what system prompt the tidier LLM receives, using a script you can edit freely.

---

## How it works

When a recording finishes, TinyWhisper runs your script **before** sending text to the LLM. The script prints the system prompt to stdout. The LLM then cleans the transcription using that prompt.

```
[transcription] → your script → [system prompt] → LLM → [cleaned text]
```

TinyWhisper sets one environment variable for the script:

| Variable   | Contents                          |
|------------|-----------------------------------|
| `$TW_TEXT` | The raw transcription text        |

Print your system prompt to **stdout**. Exit non-zero, or print nothing, to fall back to the built-in default prompt.

---

## Supported script types

| Extension | Interpreter  |
|-----------|-------------|
| `.py`     | `python3`   |
| `.sh`     | `bash`      |
| `.js`     | `node`      |

If the file is executable (`chmod +x`), it is invoked directly regardless of extension.

---

## The bundled script: `claude-context.py`

`claude-context.py` is seeded here automatically on first launch. It:

1. Finds the most recently modified **Claude Code** session log (`~/.claude/projects/**/*.jsonl`)
2. Extracts the last 10 messages from that session
3. Injects them as `<additional_context>` into the system prompt

This means the LLM can recognise project-specific terms, names, and jargon from your current work session — so "Parake" becomes "Parakeet", "Quen" becomes "Qwen", and so on.

You can edit `claude-context.py` freely. It will **not** be overwritten once it exists.

---

## Writing your own script

Create any `.py`, `.sh`, or `.js` file in this folder and point Advanced Settings → Tidier → Prompt Script at it.

**Minimal example** (`my-prompt.sh`):

```bash
#!/usr/bin/env bash
echo "Fix capitalization and punctuation only. Return the cleaned text."
```

**Example using `$TW_TEXT`** (`smart-prompt.py`):

```python
#!/usr/bin/env python3
import os
text = os.environ.get("TW_TEXT", "")
# Detect code-heavy input and adjust the prompt
if any(c in text for c in ("def ", "const ", "import ")):
    print("This is a code dictation. Fix grammar only; preserve all technical terms exactly.")
else:
    print("Fix capitalization, punctuation, and remove filler words. Return only the cleaned text.")
```

---

## Tips

- Keep the prompt short and direct — small models (1–2B) follow concise instructions better than long ones.
- Always end with "Return ONLY the cleaned text" or equivalent — without it, models tend to add commentary.
- The script has a **15-second timeout**. If it exceeds this, TinyWhisper falls back to the built-in default.
