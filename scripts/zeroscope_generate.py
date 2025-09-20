#!/usr/bin/env python3
"""
Minimal ZeroScope text-to-video generation using Diffusers.

Defaults are conservative for Apple Silicon (MPS) and short clips.

Requirements (resolved via `uv run --with ...`):
  - torch (with MPS support), diffusers, transformers, accelerate, imageio[ffmpeg]

Usage example:
  uv run --with torch diffusers transformers accelerate "imageio[ffmpeg]" \
    scripts/zeroscope_generate.py \
    --model-path models/cerspense/zeroscope_v2_576w \
    --prompt "a timelapse of clouds over mountains" \
    --frames 16 --width 576 --height 320 --steps 20 --guidance 9.0 \
    --out out/zero.mp4

If ffmpeg is unavailable, frames are written as PNGs under the output stem dir.
"""
from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path
from typing import List
import numpy as np
from PIL import Image


def have_ffmpeg() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        return True
    except FileNotFoundError:
        return False


def _normalize_hwcn(arr: np.ndarray) -> np.ndarray:
    """Normalize a frame to HxWxC uint8.

    Handles shapes like (T,H,W,C), (1,1,H,W,C), (C,H,W), (H,W,C), (H,W), etc.
    """
    a = np.asarray(arr)
    # Remove all singleton dims
    a = np.squeeze(a)
    # If still more than 3 dims, take the last 3 (assume time/batch leading)
    if a.ndim > 3:
        a = a.reshape(a.shape[-3], a.shape[-2], a.shape[-1])
    # Promote grayscale to RGB
    if a.ndim == 2:
        a = np.stack([a, a, a], axis=-1)
    elif a.ndim == 3:
        # Ensure channel-last
        if a.shape[-1] not in (1, 3):
            if a.shape[0] in (1, 3):
                a = np.moveaxis(a, 0, -1)
            elif a.shape[1] in (1, 3):
                a = np.moveaxis(a, 1, -1)
        # If single-channel, replicate to RGB
        if a.shape[-1] == 1:
            a = np.repeat(a, 3, axis=-1)
    else:
        # Fallback: try to coerce to HWC
        a = np.atleast_3d(a)
        if a.shape[-1] not in (1, 3) and a.shape[0] in (1, 3):
            a = np.moveaxis(a, 0, -1)
    # Cast/scale to uint8
    if a.dtype == np.uint8:
        return a
    a = np.nan_to_num(a, nan=0.0, posinf=1.0, neginf=0.0)
    if np.issubdtype(a.dtype, np.floating):
        a = (np.clip(a, 0.0, 1.0) * 255.0).astype(np.uint8)
    else:
        a = np.clip(a, 0, 255).astype(np.uint8)
    return a


def _to_uint8_frames(frames: List) -> List[np.ndarray]:
    return [_normalize_hwcn(np.array(f) if isinstance(f, Image.Image) else np.asarray(f)) for f in frames]


def _flatten_frames(seq: List) -> List[np.ndarray]:
    """Flatten a sequence so each element is a single frame (HWC or convertible).

    Handles cases where elements are stacked (T,H,W,C) or have extra batch dims.
    """
    flat: List[np.ndarray] = []
    for f in seq:
        a = np.asarray(f)
        # If more than 3 dims and first dim > 1, assume it's a stack of frames
        while a.ndim > 3 and a.shape[0] == 1:
            a = np.squeeze(a, axis=0)
        if a.ndim > 3 and a.shape[0] > 1:
            for i in range(a.shape[0]):
                flat.append(a[i])
        else:
            flat.append(a)
    return flat


def export_frames_to_video(frames: List, out_path: Path, fps: int = 8) -> None:
    frames = _flatten_frames(frames)
    u8_frames = _to_uint8_frames(frames)
    try:
        from diffusers.utils import export_to_video  # type: ignore
        export_to_video(u8_frames, out_path, fps=fps)
        return
    except Exception:
        pass

    # Fallback to ffmpeg CLI if available
    if have_ffmpeg():
        tmp_dir = out_path.parent / (out_path.stem + "_frames")
        tmp_dir.mkdir(parents=True, exist_ok=True)
        for i, arr in enumerate(u8_frames):
            Image.fromarray(arr).save(tmp_dir / f"frame_{i:04d}.png")
        subprocess.run([
            "ffmpeg", "-y", "-framerate", str(fps), "-i", str(tmp_dir / "frame_%04d.png"),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out_path)
        ], check=True)
    else:
        # Last resort: write PNGs next to the requested output path
        out_dir = out_path.parent / (out_path.stem + "_frames")
        out_dir.mkdir(parents=True, exist_ok=True)
        for i, arr in enumerate(u8_frames):
            Image.fromarray(arr).save(out_dir / f"frame_{i:04d}.png")


def main() -> int:
    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", required=True, help="Local path to ZeroScope 576w snapshot")
    parser.add_argument("--prompt", required=True, help="Text prompt")
    parser.add_argument("--frames", type=int, default=16, help="Number of frames")
    parser.add_argument("--width", type=int, default=576)
    parser.add_argument("--height", type=int, default=320)
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--guidance", type=float, default=9.0)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--out", default="out/zeroscope.mp4", help="Output video path (.mp4)")
    parser.add_argument("--negative", default=None, help="Negative prompt terms (e.g., 'monochrome, grayscale, blue tint, low saturation')")
    parser.add_argument("--style", default=None, help="Positive style prefix (e.g., 'vibrant colors, daylight, balanced exposure')")
    parser.add_argument("--fps", type=int, default=8, help="Video frames per second for export")
    parser.add_argument("--scheduler", default="dpm", choices=["dpm", "euler", "ddim", "pndm", "unipc"], help="Sampler/scheduler")
    parser.add_argument("--fp32", action="store_true", help="Force float32 even on MPS/CUDA (stability over speed)")
    parser.add_argument("--save-frames-dir", default=None, help="Optional directory to also save PNG frames for debugging")
    parser.add_argument("--allow-pickle", action="store_true", help="Allow loading .bin (pickle) weights; disabled by default for safety")
    args = parser.parse_args()

    try:
        import torch  # type: ignore
        from diffusers import (
            TextToVideoSDPipeline,
            DPMSolverMultistepScheduler,
            EulerDiscreteScheduler,
            DDIMScheduler,
            PNDMScheduler,
            UniPCMultistepScheduler,
        )  # type: ignore
    except Exception as e:
        print(f"Missing dependencies: {e}")
        return 2

    device = "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
    dtype = torch.float32 if (args.fp32 or device == "cpu") else torch.float16

    # Enforce safetensors unless user explicitly opts into pickle .bin
    load_kwargs = dict(dtype=dtype, local_files_only=True)
    try:
        # These kwargs are supported in recent diffusers/hf_hub
        if not args.allow_pickle:
            load_kwargs.update({"use_safetensors": True, "allow_pickle": False})
        else:
            load_kwargs.update({"use_safetensors": False, "allow_pickle": True})
    except Exception:
        pass

    pipe = TextToVideoSDPipeline.from_pretrained(args.model_path, **load_kwargs)
    # Select scheduler
    try:
        if args.scheduler == "dpm":
            pipe.scheduler = DPMSolverMultistepScheduler.from_config(pipe.scheduler.config)
        elif args.scheduler == "euler":
            pipe.scheduler = EulerDiscreteScheduler.from_config(pipe.scheduler.config)
        elif args.scheduler == "ddim":
            pipe.scheduler = DDIMScheduler.from_config(pipe.scheduler.config)
        elif args.scheduler == "pndm":
            pipe.scheduler = PNDMScheduler.from_config(pipe.scheduler.config)
        elif args.scheduler == "unipc":
            pipe.scheduler = UniPCMultistepScheduler.from_config(pipe.scheduler.config)
    except Exception:
        pass
    # Memory-friendly toggles
    try:
        pipe.enable_attention_slicing()
        pipe.enable_vae_slicing()
    except Exception:
        pass

    if device == "cpu":
        try:
            pipe.enable_sequential_cpu_offload()
        except Exception:
            pipe.enable_model_cpu_offload()
    else:
        pipe.to(device)

    generator = torch.manual_seed(args.seed) if args.seed is not None else None

    print(f"device={device}, dtype={dtype}, frames={args.frames}, size={args.width}x{args.height}, steps={args.steps}, guidance={args.guidance}, scheduler={args.scheduler}")

    full_prompt = f"{args.style}, {args.prompt}" if args.style else args.prompt
    result = pipe(
        full_prompt,
        num_inference_steps=args.steps,
        guidance_scale=args.guidance,
        num_frames=args.frames,
        height=args.height,
        width=args.width,
        negative_prompt=(args.negative or None),
        generator=generator,
    )
    # Extract frames robustly across diffusers versions
    frames = None
    if hasattr(result, "frames"):
        frames = result.frames  # type: ignore[attr-defined]
    else:
        try:
            frames = result["frames"]  # type: ignore[index]
        except Exception:
            try:
                frames = result[0]  # type: ignore[index]
            except Exception:
                pass

    if frames is None:
        raise RuntimeError("Could not extract frames from pipeline result")

    # If a single numpy array (T,H,W,C), split into list
    if isinstance(frames, np.ndarray) and frames.ndim == 4:
        frames = [frames[i] for i in range(frames.shape[0])]

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Basic telemetry: check dynamic range
    try:
        mins = float(np.min(frames))
        maxs = float(np.max(frames))
        print(f"frames_range=[{mins:.3f}, {maxs:.3f}]")
    except Exception:
        pass

    # Optional PNG dump for inspection
    if args.save_frames_dir:
        dump_dir = Path(args.save_frames_dir)
        dump_dir.mkdir(parents=True, exist_ok=True)
        for i, arr in enumerate(_to_uint8_frames(frames)):
            Image.fromarray(arr).save(dump_dir / f"frame_{i:04d}.png")

    export_frames_to_video(frames, out_path, fps=max(1, int(args.fps)))
    print(f"Saved -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
