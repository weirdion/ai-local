# Decisions

| Date       | Decision                                                | Rationale |
|------------|---------------------------------------------------------|-----------|
| 2025-09-19 | Track required tooling via `Brewfile` + Make targets    | Keep installs reproducible, disable surprise Homebrew updates |
| 2025-09-19 | Limit model/tool pulls to trusted registries (HF/Ollama) | Reduce supply-chain risk by pinning to known orgs and verifying releases |
| 2025-09-19 | Run `make ollama-serve` in a `screen` session            | Ensure Ollama stays bound to localhost while providing a managed background service |
| 2025-09-19 | Added `ollama-chat`/`ollama-ask` helpers                 | Provide controlled CLI interaction while inheriting localhost-only bindings |
| 2025-09-19 | Hardened `ui/ollama-chat` (CSP, dark default, toggle)    | Restrict assets/API to loopback, improve readability without persisting transcripts |
| 2025-09-19 | Added `make ui-serve` for bounded UI hosting             | Serve UI with localhost bind and clear stop/start workflow |
| 2025-09-19 | Pulled `llama3.1:8b` via `make ollama-pull`             | Baseline local LLM for benchmarking; verifying SHA256 during pull ensures integrity |
