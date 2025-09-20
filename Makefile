BUNDLE_FILE := Brewfile
MODEL ?= llama3.1:8b
PROMPT ?=
UI_PORT ?= 8000
UI_BIND ?= 127.0.0.1
OLLAMA_ENV := OLLAMA_HOST=127.0.0.1:11434 OLLAMA_ORIGINS='http://127.0.0.1 http://localhost http://127.0.0.1:* http://localhost:* file://*'

.PHONY: brew-check brew-install ollama-serve ollama-pull ollama-chat ollama-ask ui-serve

brew-check:
	HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_BUNDLE_FILE=$(BUNDLE_FILE) brew bundle check --verbose

brew-install:
	HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_BUNDLE_FILE=$(BUNDLE_FILE) brew bundle install --no-upgrade

ollama-serve:
	$(OLLAMA_ENV) ollama serve

ollama-pull:
	$(OLLAMA_ENV) ollama pull $(MODEL)

ollama-chat:
	$(OLLAMA_ENV) ollama run $(MODEL)

ollama-ask:
	@if [ -z "$(strip $(PROMPT))" ]; then \
		echo "PROMPT variable is required. Example: make ollama-ask PROMPT='Say hi'" >&2; \
		exit 1; \
	fi
	@printf '%s\n' "$(PROMPT)" | $(OLLAMA_ENV) ollama run $(MODEL)

ui-serve:
	@echo "Serving UI at http://$(UI_BIND):$(UI_PORT)/ollama-chat.html (Ctrl+C to stop)"
	python3 -m http.server $(UI_PORT) --bind $(UI_BIND) --directory ui

# --- Hugging Face Hub (isolated cache + pinned downloads) ---
HF_REPO ?=
HF_REV ?=
HF_INCLUDE ?= *.safetensors,*.json
HF_ENV := HF_HOME=$(PWD)/.cache/huggingface HUGGINGFACE_HUB_CACHE=$(PWD)/.cache/huggingface/hub

.PHONY: hf-login hf-whoami hf-download hf-safe-download

hf-login:
	$(HF_ENV) huggingface-cli login

hf-whoami:
	$(HF_ENV) huggingface-cli whoami

# Basic CLI download (fast path). Example:
# make hf-download HF_REPO=stabilityai/stable-diffusion-2-1 HF_REV=main
hf-download:
	@if [ -z "$(strip $(HF_REPO))" ] || [ -z "$(strip $(HF_REV))" ]; then \
		echo "HF_REPO and HF_REV are required" >&2; \
		exit 2; \
	fi
	$(HF_ENV) huggingface-cli download $(HF_REPO) --revision $(HF_REV) \
	  --include "$(HF_INCLUDE)" --local-dir models/$(HF_REPO) --local-dir-use-symlinks False

# Safe snapshot + lockfile. Example:
# make hf-safe-download HF_REPO=stabilityai/stable-diffusion-2-1 HF_REV=5c9d0c0
hf-safe-download:
	@if [ -z "$(strip $(HF_REPO))" ] || [ -z "$(strip $(HF_REV))" ]; then \
		echo "HF_REPO and HF_REV are required" >&2; \
		exit 2; \
	fi
	$(HF_ENV) uv run --with huggingface_hub scripts/hf_download.py \
	  --repo $(HF_REPO) --revision $(HF_REV) --include "$(HF_INCLUDE)" --dest models

# --- Cleanup helpers ---
.PHONY: hf-clean hf-scan-cache hf-clean-cache ollama-clean ollama-prune uv-clean-cache clean-all

# Remove a specific local snapshot + its lockfile
# Usage: make hf-clean HF_REPO=org/name
hf-clean:
	@if [ -z "$(strip $(HF_REPO))" ]; then \
		echo "HF_REPO is required (e.g., stabilityai/stable-diffusion-2-1)" >&2; \
		exit 2; \
	fi
	rm -rf "models/$(HF_REPO)" "models/$(HF_REPO).lock.json" || true
	@echo "Removed models/$(HF_REPO) and lockfile if present."

# Inspect and clean the scoped Hugging Face cache under .cache/huggingface
hf-scan-cache:
	HUGGINGFACE_HUB_CACHE=$(PWD)/.cache/huggingface/hub huggingface-cli scan-cache || true

hf-clean-cache:
	HUGGINGFACE_HUB_CACHE=$(PWD)/.cache/huggingface/hub huggingface-cli delete-cache --yes || true
	@echo "Cleared .cache/huggingface/hub"

# Ollama model cleanup (requires local server)
# Usage: make ollama-clean OLLAMA_MODEL=llama3.1:8b
ollama-clean:
	@if [ -z "$(strip $(OLLAMA_MODEL))" ]; then \
		echo "OLLAMA_MODEL is required (e.g., llama3.1:8b)" >&2; \
		exit 2; \
	fi
	OLLAMA_HOST=127.0.0.1:11434 ollama rm "$(OLLAMA_MODEL)"

ollama-prune:
	OLLAMA_HOST=127.0.0.1:11434 ollama prune

# uv cache cleanup (wheels, downloads)
uv-clean-cache:
	uv cache prune || true

# Danger: remove local HF snapshots and caches, prune uv + Ollama
# Usage: make clean-all CONFIRM=1
clean-all:
	@if [ "$(CONFIRM)" != "1" ]; then \
		echo "This will remove models/ and .cache/huggingface, prune uv cache, and run 'ollama prune'."; \
		echo "Re-run with CONFIRM=1 to proceed: make clean-all CONFIRM=1"; \
		exit 2; \
	fi
	rm -rf models || true
	rm -rf .cache/huggingface || true
	uv cache prune || true
	OLLAMA_HOST=127.0.0.1:11434 ollama prune || true
	@echo "Cleaned local snapshots, caches, and pruned Ollama + uv."

# --- ZeroScope helpers ---
.PHONY: zeroscope-download zeroscope-generate

ZEROSCOPE_REPO ?= cerspense/zeroscope_v2_576w
ZEROSCOPE_REV ?= main
ZEROSCOPE_OUT ?= out/zeroscope.mp4
ZEROSCOPE_PROMPT ?= vibrant sunlit coastal city skyline, gentle clouds moving, wide shot, vibrant natural colors, daylight, balanced exposure, no filters
ZEROSCOPE_FRAMES ?= 12
ZEROSCOPE_WIDTH ?= 384
ZEROSCOPE_HEIGHT ?= 224
ZEROSCOPE_STEPS ?= 20
ZEROSCOPE_GUIDANCE ?= 7.5
ZEROSCOPE_SCHEDULER ?= euler
ZEROSCOPE_FP32 ?= 1
ZEROSCOPE_SAVE_FRAMES ?=
ZEROSCOPE_FPS ?= 8
ZEROSCOPE_ALLOW_BIN ?= 1
ZEROSCOPE_ALLOW_PICKLE ?= 1
ZEROSCOPE_SEED ?= 42
ZEROSCOPE_NEGATIVE ?= monochrome, grayscale, blue tint, low saturation, dull colors, underexposed, dark, heavy vignette
ZEROSCOPE_STYLE ?= cartoon, cel-shaded, vibrant colors, bold outlines, dynamic lighting, exaggerated features

zeroscope-download:
	INCL=$$( if [ "$(ZEROSCOPE_ALLOW_BIN)" = "1" ]; then echo '*.safetensors,*.json,*.txt,*.bin'; else echo '*.safetensors,*.json,*.txt'; fi ); \
	$(MAKE) hf-safe-download HF_REPO=$(ZEROSCOPE_REPO) HF_REV=$(ZEROSCOPE_REV) HF_INCLUDE="$$INCL"

zeroscope-generate:
	PYTORCH_ENABLE_MPS_FALLBACK=1 \
	uv run \
	  --with torch \
	  --with diffusers \
	  --with transformers \
	  --with accelerate \
	  --with protobuf \
	  --with 'imageio[ffmpeg]' \
	  scripts/zeroscope_generate.py \
	  --model-path models/$(ZEROSCOPE_REPO) \
	  --prompt "$(ZEROSCOPE_PROMPT)" \
	  --frames $(ZEROSCOPE_FRAMES) \
	  --width $(ZEROSCOPE_WIDTH) --height $(ZEROSCOPE_HEIGHT) \
	  --steps $(ZEROSCOPE_STEPS) --guidance $(ZEROSCOPE_GUIDANCE) \
	  --scheduler $(ZEROSCOPE_SCHEDULER) \
	  $(if $(filter 1,$(ZEROSCOPE_FP32)),--fp32,) \
	  $(if $(ZEROSCOPE_SAVE_FRAMES),--save-frames-dir $(ZEROSCOPE_SAVE_FRAMES),) \
	  $(if $(filter 1,$(ZEROSCOPE_ALLOW_PICKLE)),--allow-pickle,) \
	  $(if $(ZEROSCOPE_SEED),--seed $(ZEROSCOPE_SEED),) \
	  $(if $(ZEROSCOPE_NEGATIVE),--negative "$(ZEROSCOPE_NEGATIVE)",) \
	  $(if $(ZEROSCOPE_STYLE),--style "$(ZEROSCOPE_STYLE)",) \
	  --fps $(ZEROSCOPE_FPS) \
	  --out $(ZEROSCOPE_OUT)

# --- Stable Diffusion comic (text -> multi-image grid) ---
.PHONY: comic-download comic-generate

COMIC_REPO ?= stabilityai/stable-diffusion-2-1
COMIC_REV ?= main
COMIC_WIDTH ?= 512
COMIC_HEIGHT ?= 512
COMIC_STEPS ?= 40
COMIC_GUIDANCE ?= 6.5
COMIC_ROWS ?= 1
COMIC_COLS ?= 3
COMIC_PROMPTS ?= a city skyline at dawn; a hero leaps across rooftops in the city; a mysterious figure watches from a rooftop
COMIC_OUT ?= out/comic.png
COMIC_FP32 ?= 0
COMIC_NEGATIVE ?= blurry, lowres, deformed, disfigured, extra limbs, extra fingers, mutated, watermark, text, logo, worst quality, low quality
COMIC_SCHEDULER ?= euler
COMIC_SEED ?= 20
COMIC_STYLE ?= comic book style, bold ink outlines, halftone shading, consistent palette, flat colors
COMIC_VARIANTS ?= 3
COMIC_INIT_FROM_FIRST ?= 0
COMIC_STRENGTH ?= 0.6
COMIC_CLIP_SCORE ?= 1
COMIC_CLIP_MODEL ?= openai/clip-vit-base-patch32

comic-download:
	$(MAKE) hf-safe-download HF_REPO=$(COMIC_REPO) HF_REV=$(COMIC_REV) HF_INCLUDE='*.safetensors,*.json,*.txt'

comic-generate:
	uv run \
	  --with torch \
	  --with diffusers \
	  --with transformers \
	  --with accelerate \
	  --with pillow \
	  scripts/sd_comic.py \
	  --model-path models/$(COMIC_REPO) \
	  --prompts "$(COMIC_PROMPTS)" \
	  --rows $(COMIC_ROWS) --cols $(COMIC_COLS) \
	  --width $(COMIC_WIDTH) --height $(COMIC_HEIGHT) \
	  --steps $(COMIC_STEPS) --guidance $(COMIC_GUIDANCE) \
	  $(if $(filter 1,$(COMIC_FP32)),--fp32,) \
	  $(if $(COMIC_NEGATIVE),--negative "$(COMIC_NEGATIVE)",) \
	  --seed $(COMIC_SEED) \
	  --scheduler $(COMIC_SCHEDULER) \
	  $(if $(COMIC_STYLE),--style "$(COMIC_STYLE)",) \
	  --variants $(COMIC_VARIANTS) \
	  $(if $(filter 1,$(COMIC_INIT_FROM_FIRST)),--init-from-first,) \
	  --strength $(COMIC_STRENGTH) \
	  $(if $(filter 1,$(COMIC_CLIP_SCORE)),--clip-score --clip-model $(COMIC_CLIP_MODEL),) \
	  --out "$(COMIC_OUT)"
