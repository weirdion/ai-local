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
