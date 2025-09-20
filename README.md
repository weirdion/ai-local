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
   The target pins `OLLAMA_HOST=127.0.0.1:11434` and the allowed origins (`127.0.0.1`, `localhost`, `file://*`) so the API stays loopback-only. You can detach with `Ctrl+A, D` and later reattach.
2. From another shell, pull trusted model tags with:
   ```bash
   make ollama-pull MODEL=llama3.1:8b
   ```
   After pulling, confirm the catalog with `OLLAMA_HOST=127.0.0.1:11434 ollama list` and record the exact tag + digest in `DECISIONS.md` if you adopt it.
3. When you want Ollama to run automatically at boot instead, consider `brew services start ollama` but keep the host binding and origins restricted.

For Hugging Face models, prefer `uv` virtual environments plus `huggingface-cli download --revision <tag>` so you can verify checksums before execution.

## CLI interaction helpers

- Interactive chat (maintains context until you exit):
  ```bash
  make ollama-chat MODEL=llama3.1:8b
  ```
- One-off prompt without keeping the session alive:
  ```bash
  make ollama-ask MODEL=llama3.1:8b PROMPT='Summarise the Brewfile policy'
  ```

Both targets inherit the same localhost bindings as `ollama-serve` so requests never leave the machine. When piping prompts, review the output before copying anywhere sensitive.

## Minimal web UI

A throwaway web client lives in `ui/ollama-chat.html`. It runs entirely in the browser session and keeps conversation state in memory only. The page enforces a strict Content Security Policy (self-only assets, explicit `127.0.0.1` network access) and omits persistent storage. Dark mode is enabled by default, with an inline toggle for light mode.

```bash
make ui-serve UI_PORT=8000
open http://127.0.0.1:8000/ollama-chat.html
```

Features:
- Keyboard shortcut: `⌘/Ctrl+Enter` submits the prompt (mirrors the button label).
- Token telemetry: prompt, completion, and context buffer counts are shown after each reply so you can gauge remaining headroom versus the model’s context length. Ollama will evict the oldest tokens once the configured context window (`OLLAMA_CONTEXT_LENGTH`, default aligns with the model’s `num_ctx`) is exceeded, so watch the counter if you need earlier turns.

Shut the server with `Ctrl+C` and close the tab to drop the session. Avoid serving the page from anything broader than `127.0.0.1`; if you must expose it elsewhere, audit the CSP and the hosting stack first.

## Security notes

- Only install dependencies listed in the `Brewfile`. If you need something new, add it intentionally and capture the rationale in `DECISIONS.md`.
- Before pulling model weights or new tools, read the upstream release notes and validate signatures or checksums when provided.
- Keep Ollama bound to localhost unless you deliberately expose it behind secure authentication.
- Snapshot your current taps and formula versions with `brew bundle dump --force --file Brewfile.full` when you want a full inventory separate from the curated list.
- When hosting the web UI, ensure it is served via `make ui-serve` (loopback bind) so CSP headers are respected and no additional directories are exposed.

## Hugging Face integration (local, pinned)

Keep Hugging Face data isolated and reproducible:

- Login (optional for gated repos):
  ```bash
  make hf-login
  ```
- Quick download into `models/<org>/<name>` (isolated cache under `.cache/huggingface`):
  ```bash
  make hf-download HF_REPO=stabilityai/stable-diffusion-2-1 HF_REV=main
  ```
- Safe snapshot with lockfile (records commit + file hashes):
  ```bash
  make hf-safe-download HF_REPO=stabilityai/stable-diffusion-2-1 HF_REV=5c9d0c0
  # creates models/stabilityai/stable-diffusion-2-1.lock.json
  ```

Notes
- Only pull from trusted orgs; review model cards and licenses before use.
- Prefer specific commits/tags for `HF_REV` to keep runs reproducible.
- Tokens are stored under `.cache/huggingface` (scoped to this repo) when using these targets.

### ZeroScope quickstart (text → short video)

1) Download the model snapshot (public repo):
```bash
# Safe default: include safetensors/json/txt (tokenizer merges). Some repos
# only provide pickle `.bin` weights, which are excluded by default.
make zeroscope-download

# If the model has only .bin weights, opt in explicitly (less safe):
make zeroscope-download ZEROSCOPE_ALLOW_BIN=1
```

2) Generate a short clip (Metal/MPS on Mac):
```bash
make zeroscope-generate \
  ZEROSCOPE_PROMPT='a timelapse of clouds over mountains' \
  ZEROSCOPE_FRAMES=16 ZEROSCOPE_WIDTH=576 ZEROSCOPE_HEIGHT=320 \
  ZEROSCOPE_STEPS=20 ZEROSCOPE_GUIDANCE=9.0 \
  ZEROSCOPE_OUT=out/zeroscope.mp4

# If you opted into .bin weights above, you must also allow pickle loading:
make zeroscope-generate ZEROSCOPE_ALLOW_PICKLE=1
```

Notes
- Keep frames, steps, and resolution modest on M2 Pro to avoid memory pressure.
- If `ffmpeg` is installed (Homebrew), the script writes MP4; otherwise it saves PNG frames.
- All generation runs in a `uv`-managed ephemeral environment with explicit packages.
- Security: safetensors are preferred. Loading `.bin` uses Python pickle under the hood;
  enable it only if you trust the source and have validated hashes in the lockfile.
