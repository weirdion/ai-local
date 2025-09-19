# ai-local

Local experiments for running and managing AI models on macOS.

## Homebrew dependencies

The `Brewfile` captures the minimum toolchain needed for this repo:

- `uv` for reproducible Python environments.
- `huggingface-cli` for authenticated model and dataset pulls.
- `ollama` for local model runtime.

Keep Homebrew usage consistent via the provided Make targets:

```bash
make brew-check   # verify everything in Brewfile is installed
make brew-install # install anything missing without auto-upgrading
```

These commands set `HOMEBREW_NO_AUTO_UPDATE=1` so Homebrew does not reach out to update taps in the background. Review `brew bundle install` output and hashes before accepting any downloads.

## Model workflow

1. Run the Ollama server inside an isolated session (e.g. `screen -S ollama`) so it stays up while you experiment:
   ```bash
   screen -S ollama
   make ollama-serve
   ```
   The target pins `OLLAMA_HOST=127.0.0.1:11434` and `OLLAMA_ORIGINS=127.0.0.1` so the API stays loopback-only. You can detach with `Ctrl+A, D` and later reattach.
2. From another shell, pull trusted model tags with:
   ```bash
   make ollama-pull MODEL=llama3.1:8b
   ```
   After pulling, confirm the catalog with `OLLAMA_HOST=127.0.0.1:11434 ollama list` and record the exact tag + digest in `DECISIONS.md` if you adopt it.
3. When you want Ollama to run automatically at boot instead, consider `brew services start ollama` but keep the host binding and origins restricted.

For Hugging Face models, prefer `uv` virtual environments plus `huggingface-cli download --revision <tag>` so you can verify checksums before execution.

## Security notes

- Only install dependencies listed in the `Brewfile`. If you need something new, add it intentionally and capture the rationale in `DECISIONS.md`.
- Before pulling model weights or new tools, read the upstream release notes and validate signatures or checksums when provided.
- Keep Ollama bound to localhost unless you deliberately expose it behind secure authentication.
- Snapshot your current taps and formula versions with `brew bundle dump --force --file Brewfile.full` when you want a full inventory separate from the curated list.
