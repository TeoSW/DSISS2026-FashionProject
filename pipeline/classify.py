"""
classify.py
Zero-shot garment tagging with CLIP.

For each attribute group (category, material, style, colour, sleeve, pattern) we
build a text prompt per candidate label, embed image and texts with CLIP, and
pick the label with the highest similarity. No training on anyone's images ->
commercially clean.

The image is embedded once and reused across all groups, and the text
embeddings are computed once per prompt set and cached: the prompts never
change, so recomputing them for every photo is pure waste.

Three ways to name the category:

  classify()                one softmax over all 56 categories
  classify(region="feet")   only the categories worn there, which is what the
                            API uses: the segmenter or the band crop has
                            already established where the thing is
  classify_two_stage()      ask CLIP the region first, then narrow

The narrowing exists because the flat classifier's biggest error group was
confusing garments worn on different parts of the body, and that error got much
more likely the moment the ontology grew from twelve garments to fifty-six
pieces of a whole outfit. Its cost is that a wrong region cannot be recovered
from, which evaluate.py measures and which the "what did it miss?" button is
the human answer to.

CLIP is MIT licensed.
"""

import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

from config import (
    ATTRIBUTES,
    CATEGORIES_BY_REGION,
    CATEGORY_ALIASES,
    CATEGORY_REGION,
    CLIP_MODEL,
    PROMPT_TEMPLATES,
    REGION_GROUPS,
    REGION_PROMPTS,
)

# Lazy singletons so the model loads once, on first use.
_model_name = CLIP_MODEL
_model: CLIPModel | None = None
_processor: CLIPProcessor | None = None
_text_cache: dict[str, torch.Tensor] = {}
# Off by default: averaging the six templates costs 0.8 points on the full
# validation split. It moves accuracy between classes rather than adding any.
_ensemble = False

_REGIONS = list(REGION_PROMPTS)


_aliases = True


def use_prompt_ensemble(on: bool) -> None:
    """Average every label over PROMPT_TEMPLATES, or use only the first."""
    global _ensemble
    _ensemble = on


def use_aliases(on: bool) -> None:
    """Offer CLIP the CATEGORY_ALIASES as well, folding the answer back."""
    global _aliases
    _aliases = on


def _vocabulary(group: str, region: str | None = None
                ) -> tuple[list[str], dict[str, str]]:
    """
    The words CLIP chooses from for a group, and how to fold them back.
    Only the category group has aliases; the rest answer in their own terms.

    `region` narrows the category vocabulary to the things worn there. With
    fifty-six categories a flat softmax is asked to separate a beanie from a
    pair of jeans, which is a question nobody needed answered; once the
    segmenter or the band crop has established *where* the thing is, the real
    question is only which of the nine kinds of footwear this is. The aliases
    are narrowed with it, so "trainers" survives for the feet and disappears
    everywhere else.
    """
    if group != "category":
        return ATTRIBUTES[group], {}

    labels = CATEGORIES_BY_REGION[region] if region else ATTRIBUTES[group]
    if not _aliases:
        return labels, {}
    keep = {a: t for a, t in CATEGORY_ALIASES.items()
            if region is None or CATEGORY_REGION[t] == region}
    return labels + list(keep), keep


def _fold(ranked: list[tuple[str, float]], fold: dict[str, str]
          ) -> list[tuple[str, float]]:
    """
    Collapse aliases onto their ontology label, adding up their probabilities:
    "top" and "tank top" are two ways of scoring the same answer, so the
    evidence for t-shirt is the sum, not the larger of the two.
    """
    if not fold:
        return ranked
    merged: dict[str, float] = {}
    for label, prob in ranked:
        merged[fold.get(label, label)] = merged.get(fold.get(label, label), 0.0) + prob
    return sorted(merged.items(), key=lambda kv: kv[1], reverse=True)


def use_model(name: str) -> None:
    """
    Switch checkpoint. Drops the loaded model and every cached text embedding,
    which belong to the old model's space and would otherwise be compared
    against the new model's image features.
    """
    global _model_name, _model, _processor
    if name == _model_name and _model is not None:
        return
    _model_name, _model, _processor = name, None, None
    _text_cache.clear()


def model_name() -> str:
    return _model_name


def device() -> str:
    """The GPU when there is one. Nothing here needs a choice from the caller."""
    return "cuda" if torch.cuda.is_available() else "cpu"


def _load():
    global _model, _processor
    if _model is None:
        _model = CLIPModel.from_pretrained(_model_name).to(device())
        _processor = CLIPProcessor.from_pretrained(_model_name)
        _model.eval()
    return _model, _processor


def _as_tensor(out) -> torch.Tensor:
    """
    transformers 4.x returns the projected features straight from
    get_*_features; 5.x wraps them in a BaseModelOutputWithPooling and puts them
    in pooler_output. requirements.txt pins neither, so accept both.
    """
    return out if isinstance(out, torch.Tensor) else out.pooler_output


@torch.no_grad()
def _embed(prompts: list[str]) -> torch.Tensor:
    model, processor = _load()
    inputs = processor(text=prompts, return_tensors="pt", padding=True).to(device())
    feats = _as_tensor(model.get_text_features(**inputs))
    return feats / feats.norm(dim=-1, keepdim=True)


@torch.no_grad()
def _prompt_features(key: str, prompts: list[str]) -> torch.Tensor:
    """Normalised embeddings of a fixed prompt set, computed once per model."""
    if key not in _text_cache:
        _text_cache[key] = _embed(prompts)
    return _text_cache[key]


@torch.no_grad()
def _label_features(key: str, labels: list[str]) -> torch.Tensor:
    """
    One vector per label. With ensembling, that vector is the mean of the label
    embedded under every template, renormalised: the average direction of all
    the ways of saying the same thing.
    """
    cache_key = f"{key}:{'ensemble' if _ensemble else 'single'}"
    if cache_key not in _text_cache:
        templates = PROMPT_TEMPLATES if _ensemble else PROMPT_TEMPLATES[:1]
        stacked = torch.stack([
            _embed([t.format(lbl) for lbl in labels]) for t in templates
        ])
        mean = stacked.mean(dim=0)
        _text_cache[cache_key] = mean / mean.norm(dim=-1, keepdim=True)
    return _text_cache[cache_key]


def _group_features(group: str, region: str | None = None) -> torch.Tensor:
    labels, _ = _vocabulary(group, region)
    return _label_features(f"group:{group}:{region or 'all'}:{len(labels)}", labels)


def _region_features() -> torch.Tensor:
    return _prompt_features("regions", [REGION_PROMPTS[r] for r in _REGIONS])


@torch.no_grad()
def _image_features(image: Image.Image) -> torch.Tensor:
    model, processor = _load()
    inputs = processor(images=image, return_tensors="pt").to(device())
    feats = _as_tensor(model.get_image_features(**inputs))
    return feats / feats.norm(dim=-1, keepdim=True)


def _ranked(scores: torch.Tensor, labels: list[str]) -> list[tuple[str, float]]:
    probs = scores.softmax(dim=-1)
    pairs = zip(labels, (float(p) for p in probs))
    return sorted(pairs, key=lambda kv: kv[1], reverse=True)


@torch.no_grad()
def _encode(image: Image.Image) -> tuple[torch.Tensor, torch.Tensor]:
    """Image embedding and logit scale, the two things every ranking needs."""
    model, _ = _load()
    return _image_features(image), model.logit_scale.exp()


def _rank_group(img, scale, group, region=None) -> list[tuple[str, float]]:
    labels, fold = _vocabulary(group, region)
    return _fold(_ranked((scale * img @ _group_features(group, region).T)[0], labels), fold)


def _rank_groups(img, scale, groups, region=None) -> dict[str, list[tuple[str, float]]]:
    return {group: _rank_group(img, scale, group, region)
            for group in groups or list(ATTRIBUTES)}


def rank_groups(image: Image.Image, groups: list[str] | None = None,
                region: str | None = None) -> dict[str, list[tuple[str, float]]]:
    """
    Every label of every requested group with its probability, best first:
      {"category": [("jeans", 0.83), ("trousers", 0.09), ...], "material": [...]}

    One image encoding serves all groups, which is why the evaluation can ask
    for top-1, top-3 and the material distribution without paying three times.

    `region` narrows the category vocabulary to what is worn there.
    """
    img, scale = _encode(image)
    return _rank_groups(img, scale, groups, region)


def classify(image: Image.Image, groups: list[str] | None = None,
             region: str | None = None) -> dict:
    """
    Best label per group:
      {"category": {"label": "jeans", "confidence": 0.83}, "material": {...}, ...}

    groups restricts the work to the listed attribute groups, which is what the
    evaluation script uses when only the category matters. When it is left out
    and a region is given, the groups worth asking about for that region are
    used: a pair of sneakers is never asked its sleeve length.

    `region` also narrows the category vocabulary, which is where most of the
    accuracy comes from once the ontology covers a whole outfit.
    """
    if groups is None and region:
        groups = REGION_GROUPS.get(region)
    return {
        group: {"label": ranked[0][0], "confidence": round(ranked[0][1], 3)}
        for group, ranked in rank_groups(image, groups, region).items()
    }


def rank(image: Image.Image, group: str, region: str | None = None
         ) -> list[tuple[str, float]]:
    """Every label in one group with its probability, best first."""
    return rank_groups(image, [group], region)[group]


# ---------------------------------------------------------------------------
# Region as a prior, not as a cage
#
# Narrowing the category vocabulary to the segmenter's region is most of the
# accuracy in a fifty-six category ontology, and it is also the one change that
# can turn a recoverable error into an unrecoverable one. A checked shirt whose
# upper-body mask came back hollow gets picked up by the lower-body mask
# instead, and a classifier locked to the lower body will confidently call it a
# pair of shorts -- a mistake the unrestricted classifier would never have made.
#
# So the region narrows, and then the narrowing is checked. If the best answer
# over the whole ontology lives somewhere else and beats the best in-region
# answer by a wide margin, the segmenter is overruled and the piece is refiled
# where it actually belongs.
# ---------------------------------------------------------------------------

# The overruling piece has to be at least this likely on its own, and this many
# times likelier than the best candidate the region allowed. Both, because
# either one alone fires on noise: a low-confidence winner is not evidence, and
# a large ratio between two tiny numbers is not either.
_OVERRIDE_MIN = 0.20
_OVERRIDE_MARGIN = 2.0


def _renormalised(ranked: list[tuple[str, float]], region: str
                  ) -> list[tuple[str, float]]:
    """
    The ranking restricted to one region, rescaled to sum to one.

    Rescaling is what makes the confidence mean "given that this is worn here",
    which is the honest reading of a number produced after the region was
    already decided.
    """
    kept = [(l, p) for l, p in ranked if CATEGORY_REGION.get(l) == region]
    total = sum(p for _, p in kept) or 1.0
    return [(l, p / total) for l, p in kept]


def classify_piece(image: Image.Image, region: str | None = None) -> dict:
    """
    Read one piece, using the region as a prior that can be overruled.

    Returns {tags, region, region_changed, note}. `region` is where the piece
    was finally filed, which is not always the one that was passed in; `note` is
    a sentence explaining the move when there was one, so an overrule is
    something the person reads rather than something that happens silently.

    One image encoding for the whole thing, including the cross-check: the
    unrestricted ranking is computed anyway, and the restricted one is a slice
    of it.
    """
    img, scale = _encode(image)
    everything = _rank_group(img, scale, "category", None)
    note = None
    changed = False

    if not everything:
        return {"tags": {}, "region": region, "region_changed": False, "note": None}

    best_all, best_all_p = everything[0]

    if region:
        in_region = _renormalised(everything, region)
        raw = dict(everything)
        best_in_p = raw.get(in_region[0][0], 0.0) if in_region else 0.0

        elsewhere = CATEGORY_REGION.get(best_all) != region
        if elsewhere and best_all_p >= _OVERRIDE_MIN and \
                best_all_p >= best_in_p * _OVERRIDE_MARGIN:
            note = (
                f"The segmenter cut this from the {region} body, but read on its "
                f"own it is a {best_all} ({best_all_p:.0%}), which is worn on the "
                f"{CATEGORY_REGION[best_all]}. The reading was trusted over the "
                "cut and the piece filed there instead."
            )
            region = CATEGORY_REGION[best_all]
            changed = True
    else:
        # No region came in -- the whole-image fallback ran, so nothing knows
        # where this is worn until the category says so. Deriving it here rather
        # than leaving it None is what stops a pair of joggers being asked its
        # sleeve length and then wearing the answer in its own name.
        region = CATEGORY_REGION.get(best_all)

    groups = REGION_GROUPS.get(region) if region else None
    tags = {
        group: {"label": ranked[0][0], "confidence": round(ranked[0][1], 3)}
        for group, ranked in _rank_groups(img, scale, groups, region).items()
        if group != "category" and ranked
    }
    ranked_cat = _renormalised(everything, region) if region else everything
    if ranked_cat:
        tags["category"] = {"label": ranked_cat[0][0],
                            "confidence": round(ranked_cat[0][1], 3)}

    return {"tags": tags, "region": region, "region_changed": changed,
            "note": note}


# ---------------------------------------------------------------------------
# Open-set primitives, used by pipeline.detect
#
# Everything above answers "which of these labels fits best", which always
# returns something. Finding a hat in a photograph needs the other question:
# is there anything here at all. These two give the detector a way to ask it.
# ---------------------------------------------------------------------------
def rank_labels(image: Image.Image, labels: list[str],
                templated: bool = True) -> list[tuple[str, float]]:
    """
    Rank an arbitrary label set against one image, best first.

    The detector uses this to offer a band crop the region's own categories plus
    a handful of distractors meaning "nothing is here", so a strip of bare floor
    can win outright instead of being forced to name a shoe.

    templated=False takes the strings as complete prompts rather than labels to
    be poured into PROMPT_TEMPLATES, which is what full sentences need.
    """
    img, scale = _encode(image)
    key = f"labels:{'t' if templated else 'raw'}:{hash(tuple(labels))}"
    feats = (_label_features(key, labels) if templated
             else _prompt_features(key, labels))
    return _ranked((scale * img @ feats.T)[0], labels)


def probe(image: Image.Image, positive: str, negative: str) -> float:
    """
    A yes/no question about a whole photograph, as a probability.

    Two complete sentences, a softmax over the pair, and the probability of the
    positive one. This is the standard CLIP binary probe and it is the only way
    to look for the things with no fixed place in the frame -- a belt, a watch,
    a bag over a shoulder. It is weaker than segmentation and the thresholds in
    config.py treat it as such.
    """
    return probe_many(image, [(positive, negative)])[0]


@torch.no_grad()
def probe_many(image: Image.Image,
               pairs: list[tuple[str, str]]) -> list[float]:
    """
    Twenty yes/no questions for the price of one image encoding.

    Asking probe() in a loop re-encodes the photograph once per question, which
    on a CPU is most of a second each and is the difference between the
    accessory pass costing nothing and costing twenty seconds. Each pair gets
    its own softmax, because they are twenty independent binary questions and
    not one twenty-way choice: a person can be wearing a belt and a watch.
    """
    if not pairs:
        return []
    img, scale = _encode(image)
    prompts = [p for pair in pairs for p in pair]
    feats = _prompt_features(f"probes:{hash(tuple(prompts))}", prompts)
    scores = (scale * img @ feats.T)[0]
    return [float(scores[i:i + 2].softmax(dim=-1)[0])
            for i in range(0, len(prompts), 2)]


def _two_stage(img, scale, mode: str = "prompt") -> dict:
    everything = _rank_group(img, scale, "category")

    if mode == "mass":
        # No new prompts: ask the category head, then add up its probability per
        # region and keep the heaviest one. A region can win on the strength of
        # four plausible candidates even when no single one leads.
        mass = {r: 0.0 for r in _REGIONS}
        for label, prob in everything:
            mass[CATEGORY_REGION[label]] += prob
        regions = sorted(mass.items(), key=lambda kv: kv[1], reverse=True)
    else:
        regions = _ranked((scale * img @ _region_features().T)[0], _REGIONS)

    region = regions[0][0]
    kept = [(l, p) for l, p in everything if CATEGORY_REGION.get(l) == region]
    # renormalised over the surviving labels only, so the confidence means
    # "given that this is worn here", not "out of all twelve". Rescaling the
    # probabilities is the same thing as a softmax over just those logits.
    total = sum(p for _, p in kept) or 1.0
    ranked = [(l, p / total) for l, p in kept]

    return {
        "region": region,
        "region_confidence": round(regions[0][1], 3),
        "regions": regions,
        "label": ranked[0][0],
        "confidence": round(ranked[0][1], 3),
        "ranked": ranked,
    }


def two_stage_category(image: Image.Image, mode: str = "prompt") -> dict:
    """
    Region first, then the categories that live in that region.

    mode picks how the region is decided: "prompt" asks CLIP directly with the
    sentences in REGION_PROMPTS, "mass" sums the category probabilities that
    already fall in each region. Returns the winning category with its
    probability inside the region, the region with its own score, and the
    category ranking restricted to that region, so top-k still works.
    """
    return _two_stage(*_encode(image), mode=mode)


def classify_two_stage(image: Image.Image) -> dict:
    """classify(), with the category decided in two steps instead of one."""
    img, scale = _encode(image)
    out = {
        group: {"label": r[0][0], "confidence": round(r[0][1], 3)}
        for group, r in _rank_groups(img, scale, None).items()
    }
    stage = _two_stage(img, scale)
    out["category"] = {
        "label": stage["label"],
        "confidence": stage["confidence"],
        "region": stage["region"],
        "region_confidence": stage["region_confidence"],
    }
    return out


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) != 2:
        print("usage: python -m pipeline.classify <image_path>")
        sys.exit(1)

    img = Image.open(sys.argv[1]).convert("RGB")
    print(json.dumps(classify_two_stage(img), indent=2))
