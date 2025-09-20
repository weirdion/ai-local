#!/usr/bin/env python3
"""
Generate a comic strip (grid of panels) from text prompts using Diffusers.

Features
- Loads a local Stable Diffusion snapshot (no network) via Diffusers.
- Apple Silicon (MPS) friendly: dtype control, basic memory toggles.
- Accept prompts via --prompts (semicolon/newline separated) or --prompts-file.
- Saves individual panels and a combined montage image.

Example (after downloading a model under models/...):
  uv run --with torch --with diffusers --with transformers --with accelerate --with pillow \
    scripts/sd_comic.py \
    --model-path models/stabilityai/stable-diffusion-2-1 \
    --prompts "a city skyline at dawn; a hero leaps across rooftops; a mysterious figure watches" \
    --rows 1 --cols 3 --width 512 --height 512 --steps 25 --guidance 7.5 \
    --out out/comic.png
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

import numpy as np
from PIL import Image


def parse_prompts(args) -> List[str]:
    if args.prompts_file:
        text = Path(args.prompts_file).read_text(encoding="utf-8")
        prompts = [ln.strip() for ln in text.replace("\r\n", "\n").split("\n") if ln.strip()]
    else:
        prompts = [p.strip() for p in (args.prompts or "").replace("\n", ";").split(";") if p.strip()]
    if not prompts:
        raise SystemExit("No prompts provided")
    return prompts


def make_grid(images: List[Image.Image], rows: int, cols: int, pad: int = 8, bg=(20, 20, 24)) -> Image.Image:
    assert len(images) == rows * cols, "images must match rows*cols"
    w, h = images[0].size
    grid = Image.new("RGB", (cols * w + pad * (cols - 1), rows * h + pad * (rows - 1)), color=bg)
    i = 0
    for r in range(rows):
        for c in range(cols):
            x = c * (w + pad)
            y = r * (h + pad)
            grid.paste(images[i], (x, y))
            i += 1
    return grid


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-path", required=True, help="Local path to a Stable Diffusion snapshot")
    ap.add_argument("--prompts", default=None, help="Semicolon or newline separated prompts for each panel")
    ap.add_argument("--prompts-file", default=None, help="Path to a text file with one prompt per line")
    ap.add_argument("--rows", type=int, default=1)
    ap.add_argument("--cols", type=int, default=3)
    ap.add_argument("--width", type=int, default=512)
    ap.add_argument("--height", type=int, default=512)
    ap.add_argument("--steps", type=int, default=25)
    ap.add_argument("--guidance", type=float, default=7.5)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--out", default="out/comic.png")
    ap.add_argument("--fp32", action="store_true", help="Force float32 even if GPU supports float16")
    ap.add_argument("--negative", default="", help="Negative prompt applied to all panels")
    ap.add_argument(
        "--scheduler",
        default="dpm",
        choices=["dpm", "euler", "ddim", "pndm", "unipc"],
        help="Sampler/scheduler",
    )
    ap.add_argument("--style", default="", help="Style prefix applied to every prompt (e.g. 'comic book style, bold ink, halftone')")
    ap.add_argument("--variants", type=int, default=1, help="Number of variants per panel (saves all, picks first for montage)")
    ap.add_argument("--init-from-first", action="store_true", help="Use first panel as img2img init for subsequent panels to stabilize style")
    ap.add_argument("--strength", type=float, default=0.6, help="Img2img strength when --init-from-first is used (0-1)")
    ap.add_argument("--clip-score", action="store_true", help="Rank variants per panel with CLIP and pick the best for the montage")
    ap.add_argument("--clip-model", default="openai/clip-vit-base-patch32", help="CLIP model id or local path")
    args = ap.parse_args()

    prompts = parse_prompts(args)
    n = args.rows * args.cols
    if len(prompts) < n:
        # Repeat last prompt to fill remaining panels
        prompts = prompts + [prompts[-1]] * (n - len(prompts))
    elif len(prompts) > n:
        prompts = prompts[:n]

    # Lazy imports to avoid global dependency cost
    try:
        import torch  # type: ignore
        from diffusers import (
            StableDiffusionPipeline,
            StableDiffusionImg2ImgPipeline,
            DPMSolverMultistepScheduler,
            EulerDiscreteScheduler,
            DDIMScheduler,
            PNDMScheduler,
            UniPCMultistepScheduler,
        )  # type: ignore
        # CLIP (optional)
        import torch
    except Exception as e:
        print(f"Missing dependencies: {e}")
        return 2

    device = "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
    dtype = torch.float32 if (args.fp32 or device == "cpu") else torch.float16

    pipe = StableDiffusionPipeline.from_pretrained(
        args.model_path,
        local_files_only=True,
        torch_dtype=dtype,
        safety_checker=None,
    )
    # Scheduler selection
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
    # Memory-friendly
    try:
        pipe.enable_attention_slicing()
        pipe.enable_vae_slicing()
        if device == "cpu":
            pipe.enable_sequential_cpu_offload()
    except Exception:
        pass

    pipe = pipe.to(device) if device != "cpu" else pipe

    img2img = None
    if args.init_from_first:
        # Reuse weights for img2img
        img2img = StableDiffusionImg2ImgPipeline.from_pretrained(
            args.model_path,
            local_files_only=True,
            torch_dtype=dtype,
            safety_checker=None,
        )
        try:
            if args.scheduler == "dpm":
                img2img.scheduler = DPMSolverMultistepScheduler.from_config(img2img.scheduler.config)
            elif args.scheduler == "euler":
                img2img.scheduler = EulerDiscreteScheduler.from_config(img2img.scheduler.config)
            elif args.scheduler == "ddim":
                img2img.scheduler = DDIMScheduler.from_config(img2img.scheduler.config)
            elif args.scheduler == "pndm":
                img2img.scheduler = PNDMScheduler.from_config(img2img.scheduler.config)
            elif args.scheduler == "unipc":
                img2img.scheduler = UniPCMultistepScheduler.from_config(img2img.scheduler.config)
        except Exception:
            pass
        try:
            img2img.enable_attention_slicing()
            img2img.enable_vae_slicing()
            if device == "cpu":
                img2img.enable_sequential_cpu_offload()
        except Exception:
            pass
        img2img = img2img.to(device) if device != "cpu" else img2img

    out_dir = Path(args.out).parent
    out_dir.mkdir(parents=True, exist_ok=True)

    images: List[Image.Image] = []
    clip_processor = None
    clip_model = None
    if args.clip_score:
        try:
            from transformers import CLIPProcessor, CLIPModel  # type: ignore
            clip_processor = CLIPProcessor.from_pretrained(args.clip_model, local_files_only=False)
            clip_model = CLIPModel.from_pretrained(args.clip_model, local_files_only=False)
            clip_model = clip_model.to(device if device != "cpu" else "cpu").eval()
            print(f"CLIP scoring enabled: {args.clip_model}")
        except Exception as e:
            print(f"Warning: failed to load CLIP model '{args.clip_model}': {e}. Continuing without scoring.")
            args.clip_score = False
    base_seed = args.seed if args.seed is not None else None
    for i, prompt in enumerate(prompts):
        gen = None
        if base_seed is not None:
            # Per-panel deterministic seed offset for diversity with reproducibility
            s = int(base_seed) + i
            gen = torch.Generator(device=device if device != "cpu" else None).manual_seed(s)
        full_prompt = (args.style + ", " if args.style else "") + prompt

        panel_variants: List[Image.Image] = []
        for k in range(max(1, args.variants)):
            gk = gen
            if base_seed is not None and args.variants > 1:
                gk = torch.Generator(device=device if device != "cpu" else None).manual_seed(int(base_seed) + i * 1000 + k)

            if args.init_from_first and i > 0 and len(images) > 0 and img2img is not None:
                init_img = images[0]
                res = img2img(
                    prompt=full_prompt,
                    image=init_img,
                    strength=max(0.0, min(1.0, args.strength)),
                    num_inference_steps=args.steps,
                    guidance_scale=args.guidance,
                    negative_prompt=(args.negative or None),
                    generator=gk,
                )
            else:
                res = pipe(
                    full_prompt,
                    height=args.height,
                    width=args.width,
                    num_inference_steps=args.steps,
                    guidance_scale=args.guidance,
                    negative_prompt=(args.negative or None),
                    generator=gk,
                )
            panel_img = res.images[0]
            panel_variants.append(panel_img)

        # Save variants and pick the best (by CLIP) or first for montage
        scores = []
        if args.clip_score and clip_processor is not None and clip_model is not None:
            try:
                with torch.no_grad():
                    # Score each variant against its prompt
                    for variant in panel_variants:
                        inputs = clip_processor(text=[full_prompt], images=variant, return_tensors="pt", padding=True)
                        inputs = {k: (v.to(clip_model.device) if hasattr(v, 'to') else v) for k, v in inputs.items()}
                        outputs = clip_model(**inputs)
                        img_feat = outputs.image_embeds / outputs.image_embeds.norm(p=2, dim=-1, keepdim=True)
                        txt_feat = outputs.text_embeds / outputs.text_embeds.norm(p=2, dim=-1, keepdim=True)
                        sim = (img_feat @ txt_feat.T).squeeze().item()
                        scores.append(sim)
            except Exception as e:
                print(f"Warning: CLIP scoring failed: {e}. Using first variant.")
                args.clip_score = False

        best_idx = 0
        if scores:
            best_idx = int(np.argmax(np.array(scores)))

        for idx, variant in enumerate(panel_variants, start=1):
            suffix = f"_{idx:02d}" if args.variants > 1 else ""
            panel_path = out_dir / f"panel_{i+1:02d}{suffix}.png"
            variant.save(panel_path)
        if scores:
            print(f"panel {i+1}: scores={['{:.3f}'.format(s) for s in scores]} -> best={best_idx+1}")
        images.append(panel_variants[best_idx])

    grid = make_grid(images, args.rows, args.cols)
    grid.save(args.out)
    print(f"Saved {len(images)} panels -> {out_dir}")
    print(f"Saved montage -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
