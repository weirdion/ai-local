BUNDLE_FILE := Brewfile

.PHONY: brew-check brew-install

brew-check:
	HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_BUNDLE_FILE=$(BUNDLE_FILE) brew bundle check --verbose

brew-install:
	HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_BUNDLE_FILE=$(BUNDLE_FILE) brew bundle install --no-upgrade
