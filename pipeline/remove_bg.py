"""
remove_bg.py
Background removal with rembg (U2Net). Pretrained, no training needed.

MIT (rembg) + Apache 2.0 (U2Net) -> clean for commercial use.
"""

from pathlib import Path

from PIL import Image
from rembg import remove


def cut_out(image: Image.Image) -> Image.Image:
    """
    Strip the background of an image already in memory and return RGBA,
    transparent where the background was. The evaluation crops garments out of
    Fashionpedia photos, so it never has a path to hand over.
    """
    return remove(image.convert("RGBA"))


def remove_background(image_path: str | Path) -> Image.Image:
    """Load an image from disk and strip its background."""
    with Image.open(image_path) as img:
        return cut_out(img)


def on_white(rgba: Image.Image) -> Image.Image:
    """
    Composite an RGBA cutout onto a white background and return RGB.
    CLIP expects RGB, and a plain background helps it focus on the garment.
    """
    white = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    return Image.alpha_composite(white, rgba).convert("RGB")


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("usage: python -m pipeline.remove_bg <image_path>")
        sys.exit(1)

    cut = remove_background(sys.argv[1])
    out = Path(sys.argv[1]).with_name("cutout.png")
    cut.save(out)
    print(f"saved {out}")
