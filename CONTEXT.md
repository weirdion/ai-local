# Context

This repository is for running and managing AI models locally on Mac (M2 Pro, 32 GB RAM).  
The goal is to keep experiments **secure, reproducible, and documented**.

## Why this repo exists
- To centralize setup scripts and notes (brew, Python, Hugging Face, Ollama).
- To track which models are tested, and under what conditions they run well.
- To avoid “unmanaged” installs and keep a reproducible environment.

## Hardware baseline
- MacBook Pro M2 Pro, 32 GB RAM.
- Goal: run small/medium LLMs (7B–13B).

## Current scope
- Install Ollama for curated LLMs.
- Use Hugging Face CLI for model management.
- Set up scripts for reproducibility (`Brewfile`, `Makefile`, etc.).
- Track decisions around security and isolation (no random nodes, clear repos) in `DECISIONS.md`.
- Use `README.md` as how to get started guide.
- Update `CONTEXT.md`, `DECISIONS.md` and `README.md` when appropriate.

## Future considerations
- Add ComfyUI workflows (with security notes).
- Explore Apple MLX for optimized runs.
- Pin first set of models (chat/coding/image/video).
- Document benchmarks and usability results.

## Security stance
- Models themselves are inert; risk lies in custom code.
- Keep everything in isolated environments.
- Only pull from trusted Hugging Face orgs or Ollama registry.