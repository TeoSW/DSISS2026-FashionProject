"""
remove_bg.py
Cut the garment out of a photo and drop everything else, the person included.

Two rembg models, and the difference matters here. The general u2net keeps the
salient foreground, which in a photo of someone wearing a coat is the *person*:
face, hands and hair come through with the coat. u2net_cloth_seg is trained to
segment clothing specifically, so it keeps the garment and removes the body
wearing it, which is exactly what a garment-recognition pipeline wants, both
because the model should look at cloth and not skin, and because a wardrobe of
faceless cutouts is what a wardrobe should look like.

The cloth model is preferred and the general one is the fallback: the cloth
weights are downloaded on first use, and on a machine that cannot reach the
model host that download fails, at which point removing the background badly is
better than not removing it at all.

MIT (rembg) + Apache 2.0 (U2Net) -> clean for commercial use.
"""

import os
from pathlib import Path

import numpy as np
from PIL import Image
from rembg import new_session, remove

# Hole filling needs scipy, which arrives with rembg rather than on its own. If
# a future rembg drops it the pipeline still runs: masks go through unrepaired
# and the hollow check below still throws the bad ones out.
try:
    from scipy import ndimage as _ndimage
except ImportError:  # pragma: no cover - depends on how rembg was installed
    _ndimage = None

# u2net_cloth_seg segments clothing into upper / lower / full body regions and
# returns the union, dropping the wearer. Override with REMBG_MODEL if a future
# rembg ships something better.
CLOTH_MODEL = os.getenv("REMBG_MODEL", "u2net_cloth_seg")
FALLBACK_MODEL = "u2net"

_session = None
_active_model = None


def _get_session():
    """
    The cloth-segmentation session, built once and reused. If it cannot be
    created, usually because the weights are not cached and cannot be
    downloaded, fall back to the general model and say so once rather than
    failing every upload.
    """
    global _session, _active_model
    if _session is not None:
        return _session
    for name in (CLOTH_MODEL, FALLBACK_MODEL):
        try:
            _session = new_session(name)
            _active_model = name
            if name != CLOTH_MODEL:
                print(f"remove_bg: '{CLOTH_MODEL}' unavailable, using '{name}'. "
                      "Cutouts will include the wearer, not just the clothing.")
            else:
                print(f"remove_bg: segmenting clothing with '{name}'")
            return _session
        except Exception as e:  # noqa: BLE001 - any failure means try the next
            print(f"remove_bg: could not load '{name}': {e}")
    _session = False  # tried and failed; remove() will use its own default
    return None


def active_model() -> str:
    """Which model is actually in use, for /health and the thesis writeup."""
    _get_session()
    return _active_model or "rembg default"


def cut_out(image: Image.Image) -> Image.Image:
    """
    Strip everything but the clothing and return RGBA, transparent elsewhere.
    The evaluation crops garments out of Fashionpedia photos, so it hands over
    an in-memory image and never a path.

    post_process_mask cleans the ragged edge the segmentation leaves; without it
    the cutout has a fringe of stray pixels where the body used to be.
    """
    rgba = image.convert("RGBA")
    session = _get_session()
    if session:
        return remove(rgba, session=session, post_process_mask=True)
    return remove(rgba)


# The cloth model segments into three regions in this fixed order. A garment
# occupies one of them, and a photo of a whole outfit lights up two or three.
_REGION_NAMES = ["upper", "lower", "full"]

# A region has to cover at least this share of the frame to count as a garment
# and not as a stray patch the segmentation left behind.
_MIN_COVERAGE = 0.02

# A garment fills most of the box it sits in: trousers cover the rectangle they
# occupy, and so does a jumper. A mask covering only a sliver of its own box is
# not a garment but the *outline* of one, which is what the segmentation leaves
# when it loses a dark garment against a dark background: seams and hems
# survive, the interior does not. on_white() then paints that missing interior
# white, and the classifier reads white trousers off a photo of black ones.
# Filling the interior fixes the ordinary case; whatever is still this hollow
# afterwards is not worth classifying.
_MIN_BBOX_FILL = 0.35

# Closing runs before filling because binary_fill_holes only fills a region the
# outline actually encloses; a hem broken by a few pixels leaks and nothing is
# filled at all. Five pixels seals the usual gaps without swallowing the gap
# between an arm and a torso.
_CLOSE_RADIUS = 5


def crop_to_content(rgba: Image.Image, margin: float = 0.05) -> Image.Image:
    """
    Trim transparent border so the garment fills its card instead of floating in
    a sea of empty frame. The old whole-canvas cutout put a small garment in the
    middle of a large transparent image, which is most of why the wardrobe cards
    looked wrong.
    """
    alpha = rgba.split()[-1]
    box = alpha.getbbox()
    if not box:
        return rgba
    l, t, r, b = box
    w, h = rgba.size
    mx, my = int((r - l) * margin), int((b - t) * margin)
    return rgba.crop((max(0, l - mx), max(0, t - my),
                      min(w, r + mx), min(h, b + my)))


def _bbox_fill(mask: Image.Image) -> float:
    """
    How much of its own bounding box the mask covers. Coverage measures the
    garment against the whole frame, which says how prominent it is; this
    measures it against itself, which says whether it is solid or hollow.
    """
    solid = np.asarray(mask.convert("L")) >= 128
    if not solid.any():
        return 0.0
    ys, xs = np.nonzero(solid)
    box = (ys.max() - ys.min() + 1) * (xs.max() - xs.min() + 1)
    return float(solid.sum() / box)


def _repair_mask(mask: Image.Image) -> tuple[Image.Image, bool]:
    """
    Seal the outline, then fill what it encloses.

    cut_out() gets this for free from rembg's post_process_mask, but the
    per-region masks come straight out of session.predict() and never saw it,
    and the per-region path is the one every upload takes. Returns the mask and
    whether anything was actually recovered.

    The model's own soft edge is kept where it had one: only the interior it
    dropped is forced opaque, so the cutout does not gain a hard jagged border.
    """
    if _ndimage is None:
        return mask, False
    alpha = np.asarray(mask.convert("L"))
    solid = alpha >= 128
    if not solid.any():
        return mask, False
    structure = np.ones((_CLOSE_RADIUS, _CLOSE_RADIUS), dtype=bool)
    filled = _ndimage.binary_fill_holes(
        _ndimage.binary_closing(solid, structure=structure)
    )
    if int(filled.sum()) <= int(solid.sum()):
        return mask, False
    repaired = np.maximum(alpha, filled.astype(np.uint8) * 255)
    return Image.fromarray(repaired, mode="L"), True


def _coverage(mask: Image.Image) -> float:
    hist = mask.convert("L").histogram()
    nonzero = sum(hist[16:])  # anything not near-black counts as covered
    total = mask.size[0] * mask.size[1]
    return nonzero / total if total else 0.0


def segment_garments(image: Image.Image) -> list[dict]:
    """
    Find every garment in one photo, not just the biggest.

    The cloth model already segments a picture into upper-body, lower-body and
    full-body clothing; this reads those three masks back and returns one cutout
    per region that actually contains something. A photo of a single jumper comes
    back as one garment; a photo of a whole outfit comes back as two or three,
    each cropped to itself and classified on its own.

    Each mask is repaired before use and then checked for being hollow, because
    a mask that kept only a garment's seams reads as a white garment once it is
    composited, and a wrong colour stated confidently is worse than a region
    quietly dropped.

    Returns a list of {region, cutout (RGBA, cropped), coverage, bbox_fill,
    repaired}, most prominent first. Falls back to a single whole-image cutout
    when the per-region model is not available or when every region was too
    hollow to trust, so the pipeline never comes back empty.
    """
    rgba = image.convert("RGBA")
    session = _get_session()

    regions: list[dict] = []
    if session is not None and hasattr(session, "predict"):
        try:
            masks = session.predict(image.convert("RGB"))
        except Exception as e:  # noqa: BLE001
            print(f"remove_bg: per-region predict failed ({e}); one cutout only")
            masks = []
        for name, mask in zip(_REGION_NAMES, masks):
            mask = mask.convert("L")
            if mask.size != rgba.size:
                mask = mask.resize(rgba.size)
            mask, repaired = _repair_mask(mask)
            cov = _coverage(mask)
            if cov < _MIN_COVERAGE:
                continue
            fill = _bbox_fill(mask)
            if fill < _MIN_BBOX_FILL:
                # Dropping the region is the honest move: with nothing to
                # classify the photo falls through to the whole-image cutout
                # below, whereas keeping it would hand CLIP a white rectangle
                # and store its answer as the garment's colour.
                print(f"remove_bg: '{name}' fills {fill:.0%} of its own box, "
                      "still hollow after repair; dropping it rather than "
                      "classifying the background")
                continue
            cut = rgba.copy()
            cut.putalpha(mask)
            regions.append({"region": name, "cutout": crop_to_content(cut),
                            "coverage": round(cov, 4),
                            "bbox_fill": round(fill, 4), "repaired": repaired})

    regions = _dedupe_regions(regions)
    if regions:
        regions.sort(key=lambda r: -r["coverage"])
        return regions

    # no per-region model, or nothing crossed the threshold: one cutout, whole
    return [{"region": "full", "cutout": crop_to_content(cut_out(image)),
             "coverage": 1.0}]


def _dedupe_regions(regions: list[dict]) -> list[dict]:
    """
    A one-piece and a two-piece outfit are mutually exclusive readings of the
    same photo. If 'full' dominates, it is a dress and the stray upper/lower
    scraps are dropped; if upper and lower carry the picture, the weak 'full'
    echo is dropped. Without this a dress can come back as three garments.
    """
    cov = {r["region"]: r["coverage"] for r in regions}
    full = cov.get("full", 0)
    two_piece = cov.get("upper", 0) + cov.get("lower", 0)
    if full and two_piece:
        if full >= two_piece:
            return [r for r in regions if r["region"] == "full"]
        return [r for r in regions if r["region"] != "full"]
    return regions


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
    print(f"saved {out} using {active_model()}")
