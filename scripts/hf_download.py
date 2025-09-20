#!/usr/bin/env python3
"""
Safe Hugging Face snapshot downloader with lockfile.

Features
- Pins to a specific revision/tag/commit and records the resolved commit SHA.
- Materializes files into a project-local models/ directory (no symlinks).
- Computes SHA256 for included files and writes models/<org>/<name>.lock.json.
- Uses isolated caches when HF_HOME/HUGGINGFACE_HUB_CACHE are set by the caller.

Usage (example):
  uv run --with huggingface_hub \
    scripts/hf_download.py \
    --repo stabilityai/stable-diffusion-2-1 \
    --revision 5c9d0c0 \
    --include "*.safetensors,*.json" \
    --dest models

Notes
- Authentication: set HUGGINGFACE_HUB_TOKEN (or run `huggingface-cli login`).
- Only download from trusted orgs; review licenses and model cards before use.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Iterable, List


def sha256_file(path: Path, bufsize: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(bufsize)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def parse_patterns(csv: str | None) -> List[str]:
    if not csv:
        return []
    return [p.strip() for p in csv.split(",") if p.strip()]


def main() -> int:
    try:
        from huggingface_hub import snapshot_download, model_info
    except Exception as e:  # pragma: no cover
        print(f"Missing dependency huggingface_hub: {e}", file=sys.stderr)
        return 2

    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="repo id, e.g. org/name")
    ap.add_argument("--revision", required=True, help="tag/branch/commit to pin")
    ap.add_argument("--include", default="*.safetensors,*.json", help="comma-separated allow patterns")
    ap.add_argument("--exclude", default=None, help="comma-separated ignore patterns")
    ap.add_argument("--dest", default="models", help="destination base directory")
    args = ap.parse_args()

    allow = parse_patterns(args.include)
    ignore = parse_patterns(args.exclude)

    # Resolve to a specific commit SHA for provenance
    try:
        info = model_info(args.repo, revision=args.revision)
        resolved_commit = info.sha
    except Exception as e:
        print(f"Failed to resolve model info: {e}", file=sys.stderr)
        return 1

    # Materialize into models/<org>/<name>
    org_name = args.repo
    dest_dir = Path(args.dest) / org_name
    dest_dir.mkdir(parents=True, exist_ok=True)

    try:
        snapshot_download(
            repo_id=args.repo,
            revision=resolved_commit,
            allow_patterns=allow or None,
            ignore_patterns=ignore or None,
            local_dir=str(dest_dir),
            local_dir_use_symlinks=False,
        )
    except Exception as e:
        print(f"Snapshot download failed: {e}", file=sys.stderr)
        return 1

    # Hash included files under dest_dir
    files: List[dict] = []
    for p in dest_dir.rglob("*"):
        if p.is_file():
            files.append({
                "path": str(p.relative_to(dest_dir)),
                "sha256": sha256_file(p),
                "size": p.stat().st_size,
            })

    lock = {
        "repo": args.repo,
        "revision": args.revision,
        "resolved_commit": resolved_commit,
        "allow_patterns": allow,
        "ignore_patterns": ignore,
        "dest": str(dest_dir),
        "files": files,
    }

    lock_path = dest_dir.with_suffix(".lock.json")
    with lock_path.open("w", encoding="utf-8") as f:
        json.dump(lock, f, indent=2, sort_keys=True)

    print(f"Pinned snapshot -> {dest_dir}")
    print(f"Lockfile -> {lock_path}")
    print(f"Commit: {resolved_commit}")
    print(f"Files: {len(files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

