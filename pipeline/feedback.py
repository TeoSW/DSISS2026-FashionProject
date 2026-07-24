"""
feedback.py
The correction loop: what a person says the model got wrong, kept on disk in a
form both the knowledge graph and the fine-tuner can read.

Two destinations, on purpose.

  the graph      a Correction node, and, when the garment was saved, its
                 attribute edges are re-pointed at the corrected value and
                 marked source='human'. The graph then answers the weather
                 question from the corrected facts, immediately, with no
                 retraining involved. That is the part that works today.

  the corpus     data/feedback/corrections.jsonl plus the image that produced
                 it, in a shape finetune.py can consume with --feedback. That
                 is the part that pays off later, in batches, not per click.

Be honest about the second one. One correction does not move a 151M-parameter
vision tower; a few thousand, class-balanced, do. Until then the graph carries
the correction and the model is unchanged, which is why the two paths exist
separately rather than being described as one magic loop.

The images live under data/, which is gitignored: a correction carries a
photograph somebody uploaded, and that does not belong in a public repository.
"""

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

FEEDBACK_DIR = Path("data/feedback")
CORPUS = FEEDBACK_DIR / "corrections.jsonl"
IMAGES = FEEDBACK_DIR / "images"

# a verdict is one of these; "correct" is signal too, and cheaper to give
VERDICTS = ("correct", "wrong")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def record(feedback_id: str, verdict: str, predicted: dict, corrected: dict,
           note: str = "", garment_id: str | None = None,
           model: str = "", image=None) -> dict:
    """
    Append one correction to the corpus and archive the image beside it.

    predicted is the tags dict classify() returned, corrected maps a group to
    the label the person says it should have been, e.g. {"category": "shirt"}.
    image is an optional PIL image: the archived copy is what the fine-tuner
    trains on later, so without it the record is only evidence, not data.
    """
    if verdict not in VERDICTS:
        raise ValueError(f"verdict must be one of {VERDICTS}")

    IMAGES.mkdir(parents=True, exist_ok=True)
    image_path = None
    if image is not None:
        image_path = IMAGES / f"{feedback_id}.png"
        image.convert("RGB").save(image_path)

    entry = {
        "id": feedback_id,
        "created_at": _now(),
        "verdict": verdict,
        "model": model,
        "garment_id": garment_id,
        "image": str(image_path).replace("\\", "/") if image_path else None,
        "predicted": {g: {"label": t.get("label"), "confidence": t.get("confidence")}
                      for g, t in predicted.items()},
        "corrected": corrected,
        "note": note.strip(),
    }

    CORPUS.parent.mkdir(parents=True, exist_ok=True)
    with CORPUS.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def load() -> list[dict]:
    """Every correction ever recorded, oldest first. Bad lines are skipped."""
    if not CORPUS.exists():
        return []
    rows = []
    for line in CORPUS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def summary() -> dict:
    """
    What the corpus says about the model, without asking the model anything.

    agreement is the share of judged analyses where the person pressed "right".
    It is not accuracy: people flag what annoys them and shrug at what they
    agree with, so the sample is self-selected and skews low. Reported because
    it is the honest number this loop produces, not because it replaces
    evaluate.py.
    """
    rows = load()
    per_group = Counter()
    confusions = defaultdict(Counter)
    for r in rows:
        for group, actual in (r.get("corrected") or {}).items():
            per_group[group] += 1
            predicted = (r.get("predicted") or {}).get(group, {}).get("label")
            if predicted:
                confusions[group][f"{predicted} -> {actual}"] += 1

    judged = len(rows)
    agreed = sum(1 for r in rows if r.get("verdict") == "correct")
    return {
        "total": judged,
        "confirmed": agreed,
        "corrected": judged - agreed,
        "agreement": round(agreed / judged, 3) if judged else None,
        "per_group": dict(per_group.most_common()),
        "confusions": {g: dict(c.most_common(8)) for g, c in confusions.items()},
        "with_image": sum(1 for r in rows if r.get("image")),
        "corpus": str(CORPUS).replace("\\", "/"),
    }


def training_pairs(group: str = "category") -> list[tuple[str, str]]:
    """
    (image path, label) for everything a person judged, ready for finetune.py.

    Both verdicts are used: a correction supplies the right label, a
    confirmation supplies the label the model already gave, and a confirmed
    example is still a real labelled example. Records whose image was not
    archived, or whose file has since been deleted, are dropped.
    """
    pairs = []
    for r in load():
        path = r.get("image")
        if not path or not Path(path).exists():
            continue
        label = (r.get("corrected") or {}).get(group)
        if label is None and r.get("verdict") == "correct":
            label = (r.get("predicted") or {}).get(group, {}).get("label")
        if label:
            pairs.append((path, label))
    return pairs
