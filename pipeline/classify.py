"""
classify.py
Zero-shot garment tagging with CLIP.

For each attribute group (category, material, style, colour, sleeve) we build a
text prompt per candidate label, embed image and texts with CLIP, and pick the
label with the highest similarity. No training on anyone's images -> commercially
clean.

The image is embedded once and reused across all groups, and the text
embeddings are computed once per prompt set and cached: the prompts never
change, so recomputing them for every photo is pure waste.

Two ways to name the category:

  classify()            one softmax over all 12 categories
  classify_two_stage()  region first, then only the categories in that region

The second exists because the flat classifier's biggest error group was
confusing garments worn on opposite halves of the body. Its cost is that a
wrong region cannot be recovered from, which evaluate.py measures.

CLIP is MIT licensed.
"""

import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

from config import (
    ATTRIBUTES,
    CATEGORY_ALIASES,
    CATEGORY_REGION,
    CLIP_MODEL,
    PROMPT_TEMPLATES,
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


def _vocabulary(group: str) -> tuple[list[str], dict[str, str]]:
    """
    The words CLIP chooses from for a group, and how to fold them back.
    Only the category group has aliases; the rest answer in their own terms.
    """
    labels = ATTRIBUTES[group]
    if group != "category" or not _aliases:
        return labels, {}
    return labels + list(CATEGORY_ALIASES), dict(CATEGORY_ALIASES)


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


def _load():
    global _model, _processor
    if _model is None:
        _model = CLIPModel.from_pretrained(_model_name)
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
    inputs = processor(text=prompts, return_tensors="pt", padding=True)
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


def _group_features(group: str) -> torch.Tensor:
    labels, _ = _vocabulary(group)
    return _label_features(f"group:{group}:{len(labels)}", labels)


def _region_features() -> torch.Tensor:
    return _prompt_features("regions", [REGION_PROMPTS[r] for r in _REGIONS])


@torch.no_grad()
def _image_features(image: Image.Image) -> torch.Tensor:
    model, processor = _load()
    inputs = processor(images=image, return_tensors="pt")
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


def _rank_group(img, scale, group) -> list[tuple[str, float]]:
    labels, fold = _vocabulary(group)
    return _fold(_ranked((scale * img @ _group_features(group).T)[0], labels), fold)


def _rank_groups(img, scale, groups) -> dict[str, list[tuple[str, float]]]:
    return {group: _rank_group(img, scale, group) for group in groups or list(ATTRIBUTES)}


def rank_groups(image: Image.Image, groups: list[str] | None = None
                ) -> dict[str, list[tuple[str, float]]]:
    """
    Every label of every requested group with its probability, best first:
      {"category": [("jeans", 0.83), ("trousers", 0.09), ...], "material": [...]}

    One image encoding serves all groups, which is why the evaluation can ask
    for top-1, top-3 and the material distribution without paying three times.
    """
    img, scale = _encode(image)
    return _rank_groups(img, scale, groups)


def classify(image: Image.Image, groups: list[str] | None = None) -> dict:
    """
    Best label per group:
      {"category": {"label": "jeans", "confidence": 0.83}, "material": {...}, ...}

    groups restricts the work to the listed attribute groups, which is what the
    evaluation script uses when only the category matters.
    """
    return {
        group: {"label": ranked[0][0], "confidence": round(ranked[0][1], 3)}
        for group, ranked in rank_groups(image, groups).items()
    }


def rank(image: Image.Image, group: str) -> list[tuple[str, float]]:
    """Every label in one group with its probability, best first."""
    return rank_groups(image, [group])[group]


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
