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

# --- ZeroScope helpers ---
.PHONY: zeroscope-download zeroscope-generate

ZEROSCOPE_REPO ?= cerspense/zeroscope_v2_576w
ZEROSCOPE_REV ?= main
ZEROSCOPE_OUT ?= out/zeroscope.mp4
ZEROSCOPE_PROMPT ?= "A golden retriever running through a green grass yard with a big smile on her face and ears flapping in the win"
ZEROSCOPE_FRAMES ?= 48
ZEROSCOPE_WIDTH ?= 384
ZEROSCOPE_HEIGHT ?= 216
ZEROSCOPE_STEPS ?= 12
ZEROSCOPE_GUIDANCE ?= 6.0
ZEROSCOPE_SCHEDULER ?= dpm
ZEROSCOPE_FP32 ?= 0
ZEROSCOPE_SAVE_FRAMES ?=
ZEROSCOPE_FPS ?= 8
ZEROSCOPE_ALLOW_BIN ?= 1
ZEROSCOPE_ALLOW_PICKLE ?= 1

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
	  --prompt $(ZEROSCOPE_PROMPT) \
	  --frames $(ZEROSCOPE_FRAMES) \
	  --width $(ZEROSCOPE_WIDTH) --height $(ZEROSCOPE_HEIGHT) \
	  --steps $(ZEROSCOPE_STEPS) --guidance $(ZEROSCOPE_GUIDANCE) \
	  --scheduler $(ZEROSCOPE_SCHEDULER) \
	  $(if $(filter 1,$(ZEROSCOPE_FP32)),--fp32,) \
	  $(if $(ZEROSCOPE_SAVE_FRAMES),--save-frames-dir $(ZEROSCOPE_SAVE_FRAMES),) \
	  $(if $(filter 1,$(ZEROSCOPE_ALLOW_PICKLE)),--allow-pickle,) \
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
