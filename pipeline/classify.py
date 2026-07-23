"""
classify.py
Zero-shot garment tagging with CLIP.

For each attribute group (category, material, style, color) we build a text
prompt per candidate label, embed image + texts with CLIP, and pick the label
with the highest similarity. No training on anyone's images -> commercially clean.

CLIP is MIT licensed.
"""

import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

from config import ATTRIBUTES, CLIP_MODEL, PROMPT_TEMPLATE

# Lazy singletons so the model loads once, on first use.
_model: CLIPModel | None = None
_processor: CLIPProcessor | None = None


def _load():
    global _model, _processor
    if _model is None:
        _model = CLIPModel.from_pretrained(CLIP_MODEL)
        _processor = CLIPProcessor.from_pretrained(CLIP_MODEL)
        _model.eval()
    return _model, _processor


def _best_label(image: Image.Image, labels: list[str]) -> tuple[str, float]:
    """Return the label in `labels` most similar to the image, with confidence."""
    model, processor = _load()
    prompts = [PROMPT_TEMPLATE.format(lbl) for lbl in labels]
    inputs = processor(
        text=prompts, images=image, return_tensors="pt", padding=True
    )
    with torch.no_grad():
        out = model(**inputs)
    # logits_per_image: [1, num_labels] -> softmax over labels
    probs = out.logits_per_image.softmax(dim=1)[0]
    idx = int(probs.argmax())
    return labels[idx], float(probs[idx])


def classify(image: Image.Image) -> dict:
    """
    Run every attribute group and return a dict like:
      {"category": {"label": "jeans", "confidence": 0.83}, "material": {...}, ...}
    """
    result = {}
    for group, labels in ATTRIBUTES.items():
        label, conf = _best_label(image, labels)
        result[group] = {"label": label, "confidence": round(conf, 3)}
    return result


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) != 2:
        print("usage: python -m pipeline.classify <image_path>")
        sys.exit(1)

    img = Image.open(sys.argv[1]).convert("RGB")
    print(json.dumps(classify(img), indent=2))
