BUNDLE_FILE := Brewfile
MODEL ?= llama3.1:8b
OLLAMA_ENV := OLLAMA_HOST=127.0.0.1:11434 OLLAMA_ORIGINS=127.0.0.1

.PHONY: brew-check brew-install ollama-serve ollama-pull

brew-check:
	HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_BUNDLE_FILE=$(BUNDLE_FILE) brew bundle check --verbose

brew-install:
	HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_BUNDLE_FILE=$(BUNDLE_FILE) brew bundle install --no-upgrade

ollama-serve:
	$(OLLAMA_ENV) ollama serve

ollama-pull:
	$(OLLAMA_ENV) ollama pull $(MODEL)
