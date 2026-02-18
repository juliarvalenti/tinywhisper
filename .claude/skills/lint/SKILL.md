# Lint & Type Check

Run all checks that CI runs locally.

```bash
ruff check tinywhisper/
pyright tinywhisper/
```

- `ruff` — style/lint (must pass with 0 errors)
- `pyright` — type checking (must pass with 0 errors; warnings for macOS-only imports are expected and OK)
