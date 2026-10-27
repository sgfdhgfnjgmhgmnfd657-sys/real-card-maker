#!/usr/bin/env python3
"""Validate technical consistency of a real-material effect-card delivery."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageStat


def fail(message: str, errors: list[str]) -> None:
    errors.append(message)


def image_info(path: Path) -> tuple[Image.Image, tuple[int, int], tuple[float, float] | None]:
    image = Image.open(path)
    dpi = image.info.get("dpi")
    return image.convert("RGB"), image.size, dpi


def within(value: float, expected: float, tolerance: float = 1.5) -> bool:
    return abs(value - expected) <= tolerance


def run(command: list[str]) -> str:
    try:
        return subprocess.check_output(command, text=True, stderr=subprocess.STDOUT)
    except (OSError, subprocess.CalledProcessError) as exc:
        return f"[unavailable] {exc}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--master", required=True, type=Path)
    parser.add_argument("--preview", required=True, type=Path)
    parser.add_argument("--png", required=True, type=Path)
    parser.add_argument("--jpg", required=True, type=Path)
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--dpi", type=float, default=300.0)
    parser.add_argument("--preview-diff-limit", type=float, default=8.0)
    args = parser.parse_args()

    errors: list[str] = []
    for path in (args.master, args.preview, args.png, args.jpg, args.pdf):
        if not path.is_file():
            fail(f"Missing file: {path}", errors)
    if errors:
        print("FAIL")
        print("\n".join(errors))
        return 1

    master, master_size, _ = image_info(args.master)
    print(f"master: {master_size[0]}x{master_size[1]}")
    if master_size != (4096, 2896):
        fail("Master must be 4096x2896.", errors)

    for label, path in (("PNG", args.png), ("JPG", args.jpg)):
        _, size, dpi = image_info(path)
        print(f"{label}: {size[0]}x{size[1]}, dpi={dpi}")
        if size != master_size:
            fail(f"{label} dimensions do not match master.", errors)
        if not dpi or not all(within(value, args.dpi) for value in dpi):
            fail(f"{label} is not tagged at {args.dpi:.0f} DPI.", errors)

    preview, preview_size, _ = image_info(args.preview)
    expected = master.resize(preview_size, Image.Resampling.LANCZOS)
    diff = ImageChops.difference(preview, expected)
    rms = sum(ImageStat.Stat(diff).rms) / 3
    print(f"preview: {preview_size[0]}x{preview_size[1]}, mean RMS difference={rms:.2f}")
    if abs(preview_size[0] / preview_size[1] - master_size[0] / master_size[1]) > 0.002:
        fail("Preview aspect ratio differs from master.", errors)
    if rms > args.preview_diff_limit:
        fail("Preview is not a close resize of master; check same-master export.", errors)

    pdfinfo = run(["pdfinfo", str(args.pdf)])
    pdfimages = run(["pdfimages", "-list", str(args.pdf)])
    print(pdfinfo.strip())
    print(pdfimages.strip())
    if "Page size:" not in pdfinfo or "A4" not in pdfinfo:
        fail("PDF page is not standard A4.", errors)
    if "3508" not in pdfimages or "2480" not in pdfimages:
        fail("PDF does not contain the expected 3508x2480 A4 raster.", errors)
    if "300" not in pdfimages:
        fail("PDF image PPI could not be confirmed as 300.", errors)

    if errors:
        print("FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS: dimensions, DPI tags, preview derivation, and A4 PDF raster are consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
