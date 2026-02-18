"""Optional local LLM text tidier — cleans up voice transcription output."""

from __future__ import annotations

import logging

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
        self._prompt = config.prompt or DEFAULT_PROMPT
        self._max_tokens = config.max_tokens
        self._model = None
        self._tokenizer = None

    def load(self):
        """Pre-load the model and tokenizer into memory."""
        from mlx_lm import load  # pyright: ignore[reportMissingImports]

        log.info("Loading tidier model: %s", self._model_name)
        self._model, self._tokenizer = load(self._model_name)
        log.info("Tidier model loaded.")

    def tidy(self, text: str) -> str:
        """Run the LLM to clean up transcribed text. Returns tidied text."""
        if self._model is None:
            self.load()

        from mlx_lm import generate  # pyright: ignore[reportMissingImports]

        messages = [
            {"role": "system", "content": self._prompt},
            {"role": "user", "content": text},
        ]

        if hasattr(self._tokenizer, "apply_chat_template"):
            prompt = self._tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
        else:
            # Fallback for tokenizers without chat template
            prompt = f"{self._prompt}\n\n{text}"

        result = generate(
            self._model,
            self._tokenizer,
            prompt=prompt,
            max_tokens=self._max_tokens,
        )

        tidied = result.strip()
        log.info("Tidied: %r -> %r", text, tidied)
        return tidied if tidied else text
