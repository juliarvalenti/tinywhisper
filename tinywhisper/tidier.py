"""Optional local LLM text tidier — cleans up voice transcription output."""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

from tinywhisper.config import TidierConfig

log = logging.getLogger(__name__)

DEFAULT_PROMPT = (
    "Clean up this voice transcription. Fix capitalization, punctuation, "
    "and remove filler words (um, uh, like, you know). Do not change the "
    "meaning. Return ONLY the cleaned text, nothing else."
)


class Tidier:
    """Loads a small local LLM via mlx-lm and tidies transcribed text."""

    def __init__(self, config: TidierConfig):
        self._model_name = config.model
        self._static_prompt = config.prompt or DEFAULT_PROMPT
        self._prompt_script = config.prompt_script
        self._max_tokens = config.max_tokens
        self._model = None
        self._tokenizer = None

    def _run_script(self, script: Path, text: str) -> str | None:
        """Run a prompt script and return its stdout, or None on failure.

        Supports .sh (bash), .py (python3), and .js (node) files.
        If the file is executable it is invoked directly; otherwise the
        appropriate interpreter is called based on the file extension.
        """
        env = {**os.environ, "TW_TEXT": text}
        suffix = script.suffix.lower()

        if os.access(script, os.X_OK):
            cmd = [str(script)]
        elif suffix == ".py":
            cmd = ["python3", str(script)]
        elif suffix == ".js":
            cmd = ["node", str(script)]
        else:
            cmd = ["bash", str(script)]

        try:
            r = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=15)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
            log.warning("Prompt script exited %d: %s", r.returncode, r.stderr[:300])
        except Exception as e:
            log.warning("Prompt script error: %s", e)
        return None

    def _system_prompt(self, text: str) -> str:
        """Return the system prompt — script output, static prompt, or default."""
        if self._prompt_script:
            script = Path(self._prompt_script).expanduser()
            if script.exists():
                result = self._run_script(script, text)
                if result:
                    return result
                log.warning("Prompt script failed — falling back to static prompt")
            else:
                log.warning("Prompt script not found: %s — falling back to static prompt", script)
        return self._static_prompt

    def load(self):
        """Pre-load the model and tokenizer into memory."""
        from mlx_lm import load  # pyright: ignore[reportMissingImports]

        log.info("Loading tidier model: %s", self._model_name)
        result = load(self._model_name)  # pyright: ignore[reportAssignmentType]
        self._model, self._tokenizer = result[0], result[1]
        log.info("Tidier model loaded.")

    def tidy(self, text: str) -> str:
        """Run the LLM to clean up transcribed text. Returns tidied text."""
        if self._model is None:
            self.load()
        assert self._model is not None
        assert self._tokenizer is not None

        from mlx_lm import generate  # pyright: ignore[reportMissingImports]

        messages = [
            {"role": "system", "content": self._system_prompt(text)},
            {"role": "user", "content": text},
        ]

        if hasattr(self._tokenizer, "apply_chat_template"):
            try:
                prompt = self._tokenizer.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=True,
                    enable_thinking=False,
                )
            except TypeError:
                prompt = self._tokenizer.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=True,
                )
        else:
            prompt = f"{self._prompt}\n\n{text}"

        from mlx_lm.sample_utils import make_repetition_penalty  # pyright: ignore[reportMissingImports]
        logits_processors = [make_repetition_penalty(penalty=1.3, context_size=20)]

        result = generate(
            self._model,
            self._tokenizer,
            prompt=prompt,
            max_tokens=self._max_tokens,
            logits_processors=logits_processors,
        )

        # Strip <think>...</think> blocks in case thinking mode leaked through
        import re
        result = re.sub(r"<think>.*?</think>", "", result, flags=re.DOTALL)
        tidied = result.strip()
        log.info("Tidied: %r -> %r", text, tidied)
        return tidied if tidied else text
