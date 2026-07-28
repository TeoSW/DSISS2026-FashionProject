"""
detect.py
Everything in the photograph that the cloth segmenter cannot cut out.

u2net_cloth_seg returns exactly three masks -- upper body, lower body, whole
body -- and it has never seen a shoe. So a photo of a whole outfit came back as
a jumper and a pair of jeans, and the boots, the beanie, the scarf and the bag
over the shoulder were simply not in the system's world. This module is that
missing half, and it does the job without a second detector, a second download
or a second model in memory: the CLIP encoder is already loaded, so ask it.

Two instruments, in descending order of how much they should be trusted.

  bands   A shoe is not anywhere in a photograph. It is below the trousers, and
          a hat is above the collar. The clothing masks give a bounding box, and
          a strip measured off that box is a picture of one thing. That strip is
          offered the region's own categories plus a set of distractors that
          mean "nothing is here", so an empty band can say so rather than being
          forced to name a shoe. What wins is then cut out on its own and read
          properly, which is a much better picture than the strip was.

  probes  A belt, a watch, a ring: no reliable place in the frame and often
          forty pixels wide. For these the question is a yes/no about the whole
          photograph, softmaxed against its own negation. It is the weakest
          thing here and it is held to the highest threshold.

Three outcomes, and the middle one is the point of the module:

  file    confident enough to become a garment in the knowledge graph
  speak   seen, but not confidently enough to write down -- so it is said in a
          sentence instead, and the person can confirm it in one tap
  silence below even that

A guess printed as a sentence costs the reader nothing. A guess written into the
knowledge graph costs them a wrong wardrobe.
"""

from PIL import Image

from config import (
    BAND_DISTRACTORS,
    CATEGORIES_BY_REGION,
    CATEGORY_REGION,
    DETECT_FILE,
    DETECT_SPEAK,
    DETECTION_BANDS,
    MIN_BAND_PX,
    PROBE_CARRIED_NEGATIVE,
    PROBE_CARRIED_POSITIVE,
    PROBE_CATEGORIES,
    PROBE_FILE,
    PROBE_NEGATIVE,
    PROBE_POSITIVE,
    PROBE_SPEAK,
    REGION_TITLES,
)

# A band is widened sideways relative to the clothing box, because feet stand
# wider than trousers and a hat is wider than a collar.
_BAND_WIDEN = 0.22

# Below this the isolated cutout of a band is mostly empty and the raw crop is
# the better picture: cutting out a sandal against sand sometimes returns almost
# nothing, and a poor cutout is worse than no cutout.
_MIN_CUTOUT_ALPHA = 0.04


def _band_box(clothing: tuple[int, int, int, int], size: tuple[int, int],
              anchor: str, start: float, height: float
              ) -> tuple[int, int, int, int] | None:
    """
    Where to cut a band, in image pixels.

    `start` and `height` are fractions of the clothing box's own height, so the
    geometry holds whether the photo is a full-length mirror shot or a crop from
    the waist up.
    """
    l, t, r, b = clothing
    w, h = size
    box_h = b - t
    if box_h <= 0:
        return None

    if anchor == "above":
        y1 = t - int((start + height) * box_h)
        y2 = t - int(start * box_h)
    elif anchor == "below":
        y1 = b + int(start * box_h)
        y2 = b + int((start + height) * box_h)
    else:  # within
        y1 = t + int(start * box_h)
        y2 = t + int((start + height) * box_h)

    pad = int((r - l) * _BAND_WIDEN)
    x1, x2 = max(0, l - pad), min(w, r + pad)
    y1, y2 = max(0, y1), min(h, y2)

    if x2 - x1 < MIN_BAND_PX or y2 - y1 < MIN_BAND_PX:
        return None
    return x1, y1, x2, y2


def _read_band(crop: Image.Image, region: str) -> tuple[str | None, float, float]:
    """
    What is in this band: the best category, how sure we are that anything is
    here at all, and how sure we are of which thing it is.

    The two numbers are deliberately separate. `presence` is the probability
    mass sitting on the region's categories rather than on the distractors, and
    it is what decides whether to speak at all. `identity` is the winner's share
    of that mass, renormalised, which is what "83% confident it is a boot" has
    to mean: given that something is on the feet. Collapsing them into one
    softmax over seventeen labels would make a confident reading of an obvious
    boot look like a coin flip, purely because there are nine kinds of footwear.
    """
    from pipeline import classify

    labels = CATEGORIES_BY_REGION[region]
    ranked = dict(classify.rank_labels(crop, labels + BAND_DISTRACTORS))

    mass = sum(ranked[c] for c in labels)
    if mass <= 0:
        return None, 0.0, 0.0
    best = max(labels, key=lambda c: ranked[c])
    return best, mass, ranked[best] / mass


def _isolate(crop: Image.Image):
    """
    The band's contents on their own, so the determination is read off a picture
    of the object rather than a picture of the object plus a floor.

    Returns None when the cutout came back essentially empty, in which case the
    raw crop is the honest thing to look at.
    """
    from pipeline import remove_bg

    try:
        cut = remove_bg.crop_to_content(remove_bg.cut_out(crop))
    except Exception as e:  # noqa: BLE001 - a failed cutout must not lose the band
        print(f"detect: could not isolate a band ({e})")
        return None
    alpha = cut.split()[-1]
    covered = sum(alpha.histogram()[16:]) / max(1, cut.size[0] * cut.size[1])
    return cut if covered >= _MIN_CUTOUT_ALPHA else None


def _titled(region: str) -> str:
    return REGION_TITLES.get(region, region)


def find_extras(image: Image.Image,
                clothing_box: tuple[int, int, int, int] | None,
                found_regions: set[str] | None = None) -> dict:
    """
    Look for every piece of the outfit the segmenter could not produce.

    `clothing_box` is the union bounding box of the clothing masks, from
    remove_bg.segment_garments; without one the bands cannot be placed and only
    the probes run. `found_regions` are the regions already accounted for, so
    the same jumper is not reported twice.

    Returns
      items         {region, category, confidence, presence, cutout, method}
                    for everything confident enough to file
      observations  sentences about everything seen but not confident enough to
                    write down
      probed        every probe and its probability, for the record
    """
    found = set(found_regions or ())
    items: list[dict] = []
    observations: list[str] = []
    banded: set[str] = set()          # regions a band actually looked at
    filed_regions: set[str] = set()

    # ---- bands -----------------------------------------------------------
    if clothing_box:
        for region, (anchor, start, height) in DETECTION_BANDS.items():
            if region in found:
                continue
            box = _band_box(clothing_box, image.size, anchor, start, height)
            if box is None:
                continue
            banded.add(region)
            crop = image.crop(box)
            category, presence, identity = _read_band(crop, region)
            if not category or presence < DETECT_SPEAK:
                continue

            if presence >= DETECT_FILE:
                isolated = _isolate(crop)
                items.append({
                    "region": region,
                    "category": category,
                    "confidence": round(identity, 3),
                    "presence": round(presence, 3),
                    "cutout": isolated if isolated is not None else crop.convert("RGBA"),
                    "isolated": isolated is not None,
                    "method": "band",
                })
                filed_regions.add(region)
            else:
                observations.append(
                    f"There is probably something on the {_titled(region)} — it "
                    f"reads as a {category} — but at {presence:.0%} certainty that "
                    "it is even there, it was not confident enough to file. "
                    "Say so below and it will be."
                )

    # ---- probes ----------------------------------------------------------
    # Only for what the bands could not settle. A probe that fires for a region
    # a band examined and found empty is a disagreement between two instruments,
    # and the honest thing to do with a disagreement is say it, not file it.
    pending = [c for c in PROBE_CATEGORIES
               if CATEGORY_REGION[c] not in found
               and CATEGORY_REGION[c] not in filed_regions]

    probed: dict[str, float] = {}
    if pending:
        from pipeline import classify

        pairs = []
        for category in pending:
            if CATEGORY_REGION[category] == "carried":
                pairs.append((PROBE_CARRIED_POSITIVE.format(category),
                              PROBE_CARRIED_NEGATIVE))
            else:
                pairs.append((PROBE_POSITIVE.format(category),
                              PROBE_NEGATIVE.format(category)))
        for category, score in zip(pending, classify.probe_many(image, pairs)):
            probed[category] = round(score, 3)

    # one item per region at most: a photo shows one bag, not four kinds of bag
    best_per_region: dict[str, tuple[str, float]] = {}
    for category, score in probed.items():
        region = CATEGORY_REGION[category]
        if score < PROBE_SPEAK:
            continue
        if region not in best_per_region or score > best_per_region[region][1]:
            best_per_region[region] = (category, score)

    for region, (category, score) in sorted(best_per_region.items()):
        contested = region in banded
        if score >= PROBE_FILE and not contested:
            items.append({
                "region": region,
                "category": category,
                "confidence": round(score, 3),
                "presence": round(score, 3),
                "cutout": None,
                "isolated": False,
                "method": "probe",
            })
        elif contested:
            observations.append(
                f"The whole-photo check thinks there is a {category} "
                f"({score:.0%}), but the close crop of the {_titled(region)} did "
                "not agree. Two instruments disagreeing is not a reading, so "
                "nothing was filed."
            )
        else:
            observations.append(
                f"Possibly a {category} ({score:.0%}). That is a yes/no guess "
                "about the whole photograph rather than a look at the thing "
                "itself, which is not enough to put in the wardrobe."
            )

    return {"items": items, "observations": observations, "probed": probed}
