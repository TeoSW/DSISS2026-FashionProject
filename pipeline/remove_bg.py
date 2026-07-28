"""
remove_bg.py
Cut the garment out of a photo and drop everything else, the person included.

Two sessions, because there are two different jobs.

  the cloth session   u2net_cloth_seg, the only model here that returns three
                      masks -- upper body, lower body, whole body -- instead of
                      one foreground. That split is what lets a photo of an
                      outfit come back as two garments rather than one confused
                      one, and it removes the wearer, which the general models
                      keep.

  the general session isnet-general-use, falling back to u2net. Used for the
                      whole-image cutout and, more importantly, for the band
                      crops the detector hands over: a shoe on a floor is a
                      salient object, and the cloth model has never seen one.

Accuracy work, in the order it matters:

  * alpha matting on the general path, which is what fixes the fringe of
    half-transparent pixels around hair and knitwear that a hard mask leaves
  * escalating morphological closing, so an outline broken by a few pixels is
    sealed and filled instead of the whole region being thrown away
  * a retry on a contrast-stretched copy when a mask comes back hollow, which is
    the specific failure of a dark garment against a dark background
  * speckle removal, so a stray patch of wall does not travel with the garment
  * every rejection is reported as text instead of being printed to a log
    nobody reads

MIT (rembg) + Apache 2.0 (U2Net / ISNet) -> clean for commercial use.
"""

import os
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps
from rembg import new_session, remove

# Hole filling and connected components need scipy, which arrives with rembg
# rather than on its own. If a future rembg drops it the pipeline still runs:
# masks go through unrepaired and the hollow check below still throws the bad
# ones out.
try:
    from scipy import ndimage as _ndimage
except ImportError:  # pragma: no cover - depends on how rembg was installed
    _ndimage = None

# u2net_cloth_seg segments clothing into upper / lower / full body regions and
# drops the wearer. Override with REMBG_MODEL if a future rembg ships something
# better at the same job.
CLOTH_MODEL = os.getenv("REMBG_MODEL", "u2net_cloth_seg")

# The general foreground models, best first. isnet-general-use is a clear step
# up from u2net on exactly the images the detector produces -- a single object,
# often small, on a cluttered floor -- and both are already vendored by rembg.
GENERAL_MODELS = [os.getenv("REMBG_GENERAL_MODEL", "isnet-general-use"), "u2net"]

# Alpha matting recovers the soft boundary a binary mask destroys. It costs
# roughly a second on a phone photo, which is worth it on the one or two cutouts
# an upload produces and would not be worth it on a batch of ten thousand, so
# the evaluation can switch it off.
ALPHA_MATTING = os.getenv("REMBG_MATTING", "1") != "0"

# Segmentation happens on a copy no larger than this on the long edge. A phone
# photo is 4000px wide, the models run at 320-1024, and the stored cutout does
# not need to be bigger than a wardrobe card ever shows. Capping it makes every
# upload faster and makes alpha matting affordable.
MAX_SIDE = 1600

_cloth = None
_cloth_name = None
_general = None
_general_name = None


def _fit(image: Image.Image, max_side: int = MAX_SIDE) -> Image.Image:
    """Downscale to a working size, preserving aspect. Never upscales."""
    w, h = image.size
    longest = max(w, h)
    if longest <= max_side:
        return image
    scale = max_side / longest
    return image.resize((max(1, round(w * scale)), max(1, round(h * scale))),
                        Image.LANCZOS)


def _cloth_session():
    """
    The cloth-segmentation session, built once and reused. Returns None when it
    cannot be created -- usually because the weights are not cached and cannot
    be downloaded -- and the caller falls back to a single general cutout.
    """
    global _cloth, _cloth_name
    if _cloth is not None:
        return _cloth or None
    try:
        _cloth = new_session(CLOTH_MODEL)
        _cloth_name = CLOTH_MODEL
        print(f"remove_bg: segmenting clothing with '{CLOTH_MODEL}'")
    except Exception as e:  # noqa: BLE001
        print(f"remove_bg: could not load '{CLOTH_MODEL}': {e}")
        _cloth = False
    return _cloth or None


def _general_session():
    """The general foreground session: whole-image cutouts and band crops."""
    global _general, _general_name
    if _general is not None:
        return _general or None
    for name in GENERAL_MODELS:
        try:
            _general = new_session(name)
            _general_name = name
            print(f"remove_bg: general cutouts with '{name}'")
            return _general
        except Exception as e:  # noqa: BLE001
            print(f"remove_bg: could not load '{name}': {e}")
    _general = False
    return None


def active_model() -> str:
    """Which cloth model is in use, for /health and the thesis writeup."""
    _cloth_session()
    return _cloth_name or "unavailable"


def general_model() -> str:
    _general_session()
    return _general_name or "rembg default"


def cut_out(image: Image.Image, matting: bool | None = None) -> Image.Image:
    """
    Strip everything but the subject and return RGBA, transparent elsewhere.
    The evaluation crops garments out of Fashionpedia photos, so it hands over
    an in-memory image and never a path.

    post_process_mask cleans the ragged edge the segmentation leaves; alpha
    matting then rebuilds the soft boundary that a binary mask destroyed, which
    is what stops a wool coat from coming back with a sawtooth outline.
    """
    rgba = image.convert("RGBA")
    session = _general_session()
    use_matting = ALPHA_MATTING if matting is None else matting
    kwargs = {"post_process_mask": True}
    if session:
        kwargs["session"] = session
    if use_matting:
        kwargs.update(
            alpha_matting=True,
            alpha_matting_foreground_threshold=240,
            alpha_matting_background_threshold=15,
            alpha_matting_erode_size=8,
        )
    try:
        return remove(rgba, **kwargs)
    except Exception as e:  # noqa: BLE001 - matting is the fragile part
        if use_matting:
            print(f"remove_bg: alpha matting failed ({e}); plain mask instead")
            kwargs = {"post_process_mask": True}
            if session:
                kwargs["session"] = session
            return remove(rgba, **kwargs)
        raise


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
_MIN_BBOX_FILL = 0.35

# Closing runs before filling because binary_fill_holes only fills a region the
# outline actually encloses; a hem broken by a few pixels leaks and nothing is
# filled at all. The radii escalate: five seals the usual gaps without
# swallowing the space between an arm and a torso, and the larger ones are only
# reached when five was not enough, which is better than discarding the region.
_CLOSE_RADII = (5, 9, 15)

# A connected component smaller than this share of the largest one is a speck of
# background, not part of the garment. Generous enough to keep both legs of a
# pair of trousers and both sleeves of an open jacket.
_MIN_COMPONENT_SHARE = 0.05

# When a cloth mask is unusable, its bounding box is usually still right: a
# hollow mask is the garment's outline, and an outline knows where the garment
# is even when it has lost the middle. That box is worth one more attempt with
# the general model, which is a stronger segmenter and does not care that the
# subject is clothing. A box smaller than this share of the frame is a scrap and
# not worth the second forward pass.
_MIN_RESCUE_BOX = 0.04

# What the rescue has to come back with before it is believed.
_MIN_RESCUE_ALPHA = 0.18


def _box_share(box: tuple[int, int, int, int], size: tuple[int, int]) -> float:
    w, h = size
    return ((box[2] - box[0]) * (box[3] - box[1])) / max(1, w * h)


def _rescue_region(working: Image.Image, box: tuple[int, int, int, int],
                   name: str, notes: list[str]) -> dict | None:
    """
    One more attempt at a region the cloth model could not produce.

    Crops the photograph to where the cloth model *said* the garment was and
    hands that crop to the general foreground model. It is a much easier
    question -- one object, filling most of the frame -- and it is the reason a
    dark shirt whose mask came back as an outline is a garment in the wardrobe
    rather than a silence.

    The wearer's face and hands are not in a crop of somebody's torso, which is
    what makes this safe to do here and not on the whole photograph.
    """
    pad_x = int((box[2] - box[0]) * 0.06)
    pad_y = int((box[3] - box[1]) * 0.06)
    w, h = working.size
    crop = working.crop((max(0, box[0] - pad_x), max(0, box[1] - pad_y),
                         min(w, box[2] + pad_x), min(h, box[3] + pad_y)))
    try:
        cut = cut_out(crop)
    except Exception as e:  # noqa: BLE001
        print(f"remove_bg: rescue of '{name}' failed ({e})")
        return None

    alpha = cut.split()[-1]
    covered = sum(alpha.histogram()[16:]) / max(1, cut.size[0] * cut.size[1])
    if covered < _MIN_RESCUE_ALPHA:
        return None

    notes.append(
        f"The clothing segmenter could not produce a usable mask for the {name} "
        f"body, so the photograph was cropped to where it said the garment was "
        f"and cut out again with the general model. That recovered it."
    )
    return {
        "region": name,
        "mask": None,
        "cutout": crop_to_content(cut),
        "coverage": round(covered * _box_share(box, working.size), 4),
        "bbox_fill": round(covered, 4),
        "repaired": True,
        "despeckled": 0,
        "trusted": True,
        "rescued": True,
        "box": box,
    }


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


def _coverage(mask: Image.Image) -> float:
    hist = mask.convert("L").histogram()
    nonzero = sum(hist[16:])  # anything not near-black counts as covered
    total = mask.size[0] * mask.size[1]
    return nonzero / total if total else 0.0


def mask_box(mask: Image.Image) -> tuple[int, int, int, int] | None:
    """The bounding box of everything solid in a mask, or None if it is empty."""
    solid = np.asarray(mask.convert("L")) >= 128
    if not solid.any():
        return None
    ys, xs = np.nonzero(solid)
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def _repair_mask(mask: Image.Image) -> tuple[Image.Image, bool]:
    """
    Seal the outline, then fill what it encloses.

    cut_out() gets this for free from rembg's post_process_mask, but the
    per-region masks come straight out of session.predict() and never saw it,
    and the per-region path is the one every upload takes.

    The closing radius escalates until the result is solid enough to be a
    garment. A single fixed radius meant one broken hem was the difference
    between a cutout and a dropped region, which is a lot of weight to put on
    five pixels.

    The model's own soft edge is kept where it had one: only the interior it
    dropped is forced opaque, so the cutout does not gain a hard jagged border.
    """
    if _ndimage is None:
        return mask, False
    alpha = np.asarray(mask.convert("L"))
    solid = alpha >= 128
    if not solid.any():
        return mask, False

    best = None
    for radius in _CLOSE_RADII:
        structure = np.ones((radius, radius), dtype=bool)
        filled = _ndimage.binary_fill_holes(
            _ndimage.binary_closing(solid, structure=structure)
        )
        if int(filled.sum()) <= int(solid.sum()):
            continue
        best = filled
        repaired = np.maximum(alpha, filled.astype(np.uint8) * 255)
        candidate = Image.fromarray(repaired, mode="L")
        if _bbox_fill(candidate) >= _MIN_BBOX_FILL:
            return candidate, True

    if best is None:
        return mask, False
    repaired = np.maximum(alpha, best.astype(np.uint8) * 255)
    return Image.fromarray(repaired, mode="L"), True


def _despeckle(mask: Image.Image) -> tuple[Image.Image, int]:
    """
    Drop connected components far smaller than the largest one.

    A garment is one blob, or two when a jacket hangs open and its halves do not
    touch. What it is never is the garment plus a bright patch of skirting board
    the segmentation liked. Returns the cleaned mask and how many pieces were
    removed, so the caller can say so.
    """
    if _ndimage is None:
        return mask, 0
    alpha = np.asarray(mask.convert("L"))
    solid = alpha >= 128
    labelled, count = _ndimage.label(solid)
    if count <= 1:
        return mask, 0
    sizes = _ndimage.sum(solid, labelled, range(1, count + 1))
    threshold = sizes.max() * _MIN_COMPONENT_SHARE
    keep = np.zeros(count + 1, dtype=bool)
    keep[1:] = sizes >= threshold
    kept = keep[labelled]
    dropped = int(count - keep[1:].sum())
    if not dropped:
        return mask, 0
    return Image.fromarray((alpha * kept).astype(np.uint8), mode="L"), dropped


def _predict(session, rgb: Image.Image, size: tuple[int, int]) -> list[Image.Image]:
    """Every mask the cloth model produces, normalised to one size."""
    try:
        masks = session.predict(rgb)
    except Exception as e:  # noqa: BLE001
        print(f"remove_bg: per-region predict failed ({e})")
        return []
    out = []
    for m in masks:
        m = m.convert("L")
        if m.size != size:
            m = m.resize(size, Image.LANCZOS)
        out.append(m)
    return out


def segment_garments(image: Image.Image) -> dict:
    """
    Find every garment in one photo, not just the biggest.

    Returns
      pieces        one dict per accepted region: region, cutout (RGBA, cropped
                    to itself), coverage, bbox_fill, repaired, despeckled
      notes         plain sentences about anything that was recovered or thrown
                    away, so a rejection reaches the person instead of stdout
      clothing_box  the union bounding box of everything accepted, in `image`
                    coordinates, which is what pipeline.detect builds its head
                    and feet bands from
      image         the working copy every box above refers to
      model         which cloth model answered, or None when none could

    Each mask is repaired, despeckled and then checked for being hollow, because
    a mask that kept only a garment's seams reads as a white garment once it is
    composited, and a wrong colour stated confidently is worse than a region
    quietly dropped. A hollow region gets one more chance on a contrast-stretched
    copy of the photo before it is dropped, which is the specific rescue for a
    black garment shot against a black background.

    Falls back to a single whole-image cutout when the per-region model is not
    available or when every region failed, so the pipeline never comes back empty.
    """
    working = _fit(image).convert("RGB")
    rgba = working.convert("RGBA")
    notes: list[str] = []
    session = _cloth_session()

    regions: list[dict] = []
    # channels that produced nothing usable but did say where to look, kept for
    # a second attempt once it is known what the other channels already cover
    failed: list[dict] = []

    if session is not None and hasattr(session, "predict"):
        masks = _predict(session, working, rgba.size)
        boosted: list[Image.Image] | None = None

        for index, (name, mask) in enumerate(zip(_REGION_NAMES, masks)):
            mask, repaired = _repair_mask(mask)
            # Despeckling has to come before anything is measured, not after.
            # A handful of stray pixels down by the shoes costs nothing in
            # coverage and yet stretches the bounding box from the shirt to the
            # whole figure -- and that box is what the hollowness test divides
            # by and what the rescue below crops to. Measured late, it made a
            # shirt look hollow and then handed the rescue a picture of a whole
            # person to cut out.
            mask, dropped = _despeckle(mask)
            cov = _coverage(mask)
            box = mask_box(mask)

            if cov < _MIN_COVERAGE:
                # Almost nothing came back. Usually that is the truth -- two of
                # the three regions are empty in a photo of one garment -- but
                # when the little that came back still outlines a large area,
                # the model found the garment and lost it.
                if box and _box_share(box, rgba.size) >= _MIN_RESCUE_BOX:
                    failed.append({"region": name, "box": box, "fill": None})
                continue

            fill = _bbox_fill(mask)
            if fill < _MIN_BBOX_FILL:
                # The dark-on-dark rescue. Stretching the contrast gives the
                # segmentation the edges it could not find, and it costs one
                # extra forward pass on the photos that need it and none on the
                # photos that do not.
                if boosted is None:
                    boosted = _predict(
                        session,
                        ImageOps.autocontrast(working, cutoff=(1, 1)),
                        rgba.size,
                    )
                alt = boosted[index] if index < len(boosted) else None
                if alt is not None:
                    alt, _ = _repair_mask(alt)
                    alt, _ = _despeckle(alt)
                alt_fill = _bbox_fill(alt) if alt is not None else 0.0
                if alt_fill >= _MIN_BBOX_FILL:
                    notes.append(
                        f"The {name}-body piece was too hollow to trust at "
                        f"{fill:.0%} of its own outline, and came back solid at "
                        f"{alt_fill:.0%} once the contrast was stretched. That is "
                        "the usual sign of a dark garment against a dark background."
                    )
                    mask, fill, repaired = alt, alt_fill, True
                    cov = _coverage(mask)
                    box = mask_box(mask)
                else:
                    failed.append({"region": name, "box": box, "fill": fill})
                    continue

            # Said only for a region that survived. Every channel sheds specks
            # and two of the three are usually discarded anyway; reporting all
            # of them buried the notes that matter under housekeeping.
            if dropped:
                notes.append(
                    f"{dropped} stray patch{'es' if dropped > 1 else ''} of "
                    f"background {'were' if dropped > 1 else 'was'} removed from "
                    f"the {name}-body cutout."
                )

            cut = rgba.copy()
            cut.putalpha(mask)
            regions.append({
                "region": name,
                "mask": mask,
                "cutout": crop_to_content(cut),
                "coverage": round(cov, 4),
                "bbox_fill": round(fill, 4),
                "repaired": repaired,
                "despeckled": dropped,
                "trusted": True,
                "rescued": False,
                # recomputed here, not reused from the top of the loop: the
                # contrast retry and the despeckle can both move it
                "box": mask_box(mask),
            })

    # semantic first, geometric second: the one-piece-versus-two-piece question
    # has to be asked while all three channels are still on the table, because
    # the answer depends on where the upper and lower ones sit relative to each
    # other, and the overlap pass would already have thrown one of them away
    regions = _dedupe_regions(regions, notes)
    regions = _dedupe_overlaps(regions, notes)

    # Only now, knowing what actually survived, is it worth paying for a rescue.
    # A channel that failed over ground another channel already covers is the
    # same garment seen badly, not a second garment, and cutting it out again
    # only produces a duplicate -- which is precisely how a photograph came back
    # with its trousers twice and its shirt not at all.
    for miss in failed:
        covered = next((r for r in regions
                        if _same_object(miss["box"], _box_of(r))), None)
        if covered:
            notes.append(
                f"The {miss['region']}-body channel failed over the same ground "
                f"the {covered['region']}-body one already covers, so it was "
                "treated as one garment seen badly rather than a second garment."
            )
            continue
        rescued = _rescue_region(working, miss["box"], miss["region"], notes)
        if rescued:
            regions.append(rescued)
        elif miss["fill"] is not None:
            notes.append(
                f"Something was found on the {miss['region']} body but only its "
                f"outline survived segmentation ({miss['fill']:.0%} of its own "
                "box filled), and cutting the photograph down to it did not "
                "recover the garment either, so it was dropped rather than "
                "classified: the colour read off a hollow mask is the "
                "background's, not the garment's."
            )

    regions = _dedupe_overlaps(regions, notes)

    if regions:
        regions.sort(key=lambda r: -r["coverage"])
        # a rescued region has no mask, only the box the cloth model gave before
        # it lost the garment, which is exactly as good for placing the bands
        box = _union_box([_box_of(r) for r in regions])
        for r in regions:
            r.pop("mask", None)
            r.pop("box", None)
        return {"pieces": regions, "notes": notes, "clothing_box": box,
                "image": working, "model": _cloth_name}

    notes.append(
        "The clothing segmenter found nothing it could separate, so the whole "
        "picture was cut out as one piece. Expect the wearer to be in it."
    )
    whole = crop_to_content(cut_out(working))
    return {
        # trusted=False: "full" here means "the whole picture", not "a one-piece
        # garment", so the classifier must not narrow its vocabulary to dresses
        "pieces": [{"region": "full", "cutout": whole, "coverage": 1.0,
                    "bbox_fill": 1.0, "repaired": False, "despeckled": 0,
                    "trusted": False}],
        "notes": notes,
        "clothing_box": None,
        "image": working,
        "model": None,
    }


# Two masks whose boxes overlap this much are looking at one garment. The cloth
# model routinely outlines a single long shirt in both its upper and its lower
# channel, and once a failed channel can be rescued from its own bounding box,
# that stops being a mask nobody uses and becomes the same shirt filed twice.
_MAX_OVERLAP = 0.5
_MAX_CONTAINED = 0.8


def _box_of(region: dict) -> tuple[int, int, int, int] | None:
    if region.get("box"):
        return region["box"]
    mask = region.get("mask")
    return mask_box(mask) if mask is not None else None


def _overlap(a, b) -> tuple[float, float]:
    """
    (intersection over union, the larger of the two containment shares).

    Containment has to be measured both ways round. A box covering the whole
    figure and a box covering only the trousers have a low IoU and the trousers
    are almost entirely inside the figure -- but the figure is barely inside the
    trousers, so asking the question in only one direction misses it entirely,
    and a whole-person cutout gets filed alongside the garment it contains.
    """
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    if x2 <= x1 or y2 <= y1:
        return 0.0, 0.0
    inter = (x2 - x1) * (y2 - y1)
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    union = area_a + area_b - inter
    contained = max(inter / area_a if area_a else 0.0,
                    inter / area_b if area_b else 0.0)
    return (inter / union if union else 0.0), contained


def _same_object(a, b) -> bool:
    """Whether two boxes are looking at one thing."""
    if not a or not b:
        return False
    iou, contained = _overlap(a, b)
    return iou >= _MAX_OVERLAP or contained >= _MAX_CONTAINED


def _dedupe_overlaps(regions: list[dict], notes: list[str]) -> list[dict]:
    """
    One garment, one piece, however many channels happened to find it.

    Ordered so that a real mask is preferred over a rescue and a prominent
    region over a faint one, then anything landing on top of something already
    kept is dropped. This is the geometric half of deduplication; the
    one-piece-versus-two-piece rule below is the semantic half.
    """
    ordered = sorted(regions,
                     key=lambda r: (r.get("rescued", False), -r["coverage"]))
    kept: list[dict] = []
    for region in ordered:
        box = _box_of(region)
        if box is None:
            kept.append(region)
            continue
        clash = next((o for o in kept if _same_object(box, _box_of(o))), None)
        if clash:
            notes.append(
                f"The {region['region']}-body and {clash['region']}-body masks "
                "outline the same garment, so it was counted once rather than "
                "twice. The clothing segmenter does this with anything long."
            )
            continue
        region["box"] = box
        kept.append(region)
    return kept


def _union_box(boxes) -> tuple[int, int, int, int] | None:
    boxes = [b for b in boxes if b]
    if not boxes:
        return None
    return (min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes))


# Two masks this disjoint are not one garment seen twice, they are a top and a
# bottom. Above it they are competing readings of the same thing.
_TWO_PIECE_MAX_IOU = 0.3


def _dedupe_regions(regions: list[dict], notes: list[str]) -> list[dict]:
    """
    A one-piece and a two-piece outfit are mutually exclusive readings of the
    same photo, and getting the choice wrong loses a garment.

    Comparing coverage alone was not enough. On a photograph of a shirt and a
    pair of trousers the cloth model often lights up its full-body channel as
    well, that channel covers both garments and therefore wins on area, and the
    outfit collapses into a single piece named after whichever half read more
    strongly -- the shirt simply disappears.

    So geometry decides first: if the upper and lower masks sit in different
    parts of the frame, they are two garments whatever the full-body channel
    says. Only when they overlap each other is this a genuine one-piece and the
    area comparison is meaningful.
    """
    by_region = {r["region"]: r for r in regions}
    full, upper, lower = (by_region.get("full"), by_region.get("upper"),
                          by_region.get("lower"))
    if not full or not (upper or lower):
        return regions

    if upper and lower:
        ub, lb = _box_of(upper), _box_of(lower)
        iou = _overlap(ub, lb)[0] if ub and lb else 1.0
        if iou < _TWO_PIECE_MAX_IOU:
            notes.append(
                "The upper and lower masks cover different parts of the frame, "
                "so this is a top and a bottom rather than one long garment. "
                "The full-body mask, which spans both, was dropped instead of "
                "being allowed to swallow them."
            )
            return [r for r in regions if r["region"] != "full"]

    two_piece = (upper["coverage"] if upper else 0) + \
                (lower["coverage"] if lower else 0)
    if full["coverage"] >= two_piece:
        notes.append(
            "This reads as a one-piece: the full-body mask covers more than the "
            "upper and lower ones together and they overlap each other, so those "
            "were treated as echoes of it rather than as separate garments."
        )
        return [full]
    return [r for r in regions if r["region"] != "full"]


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
    print(f"saved {out} using {general_model()}")
