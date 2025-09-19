# Decisions

| Date       | Decision                                                | Rationale |
|------------|---------------------------------------------------------|-----------|
| 2025-09-19 | Track required tooling via `Brewfile` + Make targets    | Keep installs reproducible, disable surprise Homebrew updates |
| 2025-09-19 | Limit model/tool pulls to trusted registries (HF/Ollama) | Reduce supply-chain risk by pinning to known orgs and verifying releases |
| 2025-09-19 | Run `make ollama-serve` in a `screen` session            | Ensure Ollama stays bound to localhost while providing a managed background service |
| 2025-09-19 | Pulled `llama3.1:8b` via `make ollama-pull`             | Baseline local LLM for benchmarking; verifying SHA256 during pull ensures integrity |
