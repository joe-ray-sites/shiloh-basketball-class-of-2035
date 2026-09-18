#!/usr/bin/env python3
"""
Resize team photos for the web.

Drop full-resolution photos into assets/players/ (named by jersey number) or
assets/coaches/ (named by the coach's id), then run:

    python3 resize-photos.py

What it does, per image:
  • moves the untouched original into assets/_originals/<folder>/
  • applies the EXIF rotation flag, so phone photos aren't sideways
  • strips EXIF metadata entirely — phone photos can carry GPS coordinates,
    and these are pictures of kids that end up on a shared page
  • resizes so the long edge is at most --max px (default 1200)
  • saves photos as optimized JPEG; keeps PNG only when the image genuinely
    uses transparency

Safe to re-run: anything already in _originals is skipped, so a second run
won't re-compress an image that's already been processed.

Options:
    --max 1200      longest edge, in pixels
    --quality 82    JPEG quality (1-95)
    --dry-run       report what would happen, change nothing
"""

import argparse
import shutil
import sys
from pathlib import Path

try:
    from PIL import Image, ImageOps
except ImportError:
    sys.exit("Pillow is required.  Install it with:  python3 -m pip install Pillow")

ROOT = Path(__file__).resolve().parent
TARGETS = ["assets/players", "assets/coaches"]
SUFFIXES = {".jpg", ".jpeg", ".png", ".heic", ".webp"}


def has_real_transparency(im):
    """True only if the alpha channel actually varies — a fully opaque alpha
    channel is common and shouldn't force us to keep the much larger PNG."""
    if im.mode not in ("RGBA", "LA") and "transparency" not in im.info:
        return False
    alpha = im.convert("RGBA").getchannel("A")
    return alpha.getextrema()[0] < 255


def process(path, originals_dir, max_edge, quality, dry_run):
    rel = path.name
    try:
        im = Image.open(path)
    except Exception as exc:
        return f"  !  {rel}: cannot read ({exc})"

    im = ImageOps.exif_transpose(im)          # honour the camera rotation flag
    before_px = im.size
    before_kb = path.stat().st_size / 1024

    keep_png = has_real_transparency(im)
    out_path = path.with_suffix(".png" if keep_png else ".jpg")

    longest = max(im.size)
    if longest > max_edge:
        scale = max_edge / longest
        new_size = (round(im.width * scale), round(im.height * scale))
        im = im.resize(new_size, Image.LANCZOS)

    if dry_run:
        return (f"  ·  {rel}  {before_px[0]}x{before_px[1]} {before_kb:,.0f} KB"
                f"  ->  {im.size[0]}x{im.size[1]}  {out_path.name}")

    # Preserve the original before writing anything.
    originals_dir.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(originals_dir / rel))

    # Saving through a fresh image drops EXIF (including any GPS tags).
    if keep_png:
        im.save(out_path, "PNG", optimize=True)
    else:
        im.convert("RGB").save(out_path, "JPEG", quality=quality,
                               optimize=True, progressive=True)

    after_kb = out_path.stat().st_size / 1024
    saved = 100 - (after_kb / before_kb * 100) if before_kb else 0
    return (f"  ok {rel}  {before_px[0]}x{before_px[1]} {before_kb:,.0f} KB"
            f"  ->  {im.size[0]}x{im.size[1]} {after_kb:,.0f} KB"
            f"  ({saved:.0f}% smaller)  {out_path.name}")


def main():
    ap = argparse.ArgumentParser(description="Resize team photos for the web.")
    ap.add_argument("--max", type=int, default=1200, help="longest edge in px (default 1200)")
    ap.add_argument("--quality", type=int, default=82, help="JPEG quality (default 82)")
    ap.add_argument("--dry-run", action="store_true", help="report only, change nothing")
    ap.add_argument("folders", nargs="*", default=TARGETS,
                    help="folders to process (default: assets/players assets/coaches)")
    args = ap.parse_args()

    total = 0
    for folder in args.folders:
        src = ROOT / folder
        if not src.is_dir():
            print(f"\n{folder}  (no such folder, skipping)")
            continue

        originals = ROOT / "assets" / "_originals" / Path(folder).name
        done = {p.name for p in originals.glob("*")} if originals.is_dir() else set()

        images = sorted(p for p in src.iterdir()
                        if p.is_file() and p.suffix.lower() in SUFFIXES)
        todo = [p for p in images if p.name not in done]

        print(f"\n{folder}  —  {len(todo)} to process"
              f"{f', {len(images) - len(todo)} already done' if len(images) != len(todo) else ''}")
        for path in todo:
            print(process(path, originals, args.max, args.quality, args.dry_run))
            total += 1

    if args.dry_run:
        print(f"\nDry run — nothing changed.  {total} file(s) would be processed.")
    else:
        print(f"\nDone.  {total} file(s) processed."
              f"  Originals kept in assets/_originals/.")


if __name__ == "__main__":
    main()
