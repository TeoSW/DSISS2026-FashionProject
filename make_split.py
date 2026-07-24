"""
make_split.py
Freeze a dev / test split of the Fashionpedia validation set, once.

  python make_split.py            write splits/fashionpedia_val.json
  python make_split.py --show     print the split that already exists

Why this exists: from the moment fine-tuning starts, every hyperparameter is
chosen by looking at a score. A score you optimised against is not an estimate
of anything, so half the data has to be put away before the first training run
and looked at exactly once, at the end.

Two decisions worth defending:

The unit is the image, not the garment. Fashionpedia photos carry several
annotated garments each, and two crops of the same photo share the person, the
lighting and usually the outfit. Splitting by instance would put near-duplicates
on both sides and quietly inflate the test score.

The assignment is stratified and greedy rather than random. `hoodie` has seven
instances in the whole validation set, so a coin flip can easily leave one side
with none. Images are placed one at a time into whichever side is furthest below
its quota for the rarest class that image contains.

What this split does NOT fix: the zero-shot configuration in config.py was
already chosen by looking at all 1961 instances, so the test half is not clean
with respect to those choices. It is clean from here on, which is what fine-tuning
needs. Say that plainly in the thesis rather than implying a purity the numbers
do not have.
"""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from random import Random

from evaluate import build_tasks, load_annotations

OUT = Path("splits/fashionpedia_val.json")
SEED = 20260724
DEV_SHARE = 0.6


def build() -> dict:
    tasks, _ = build_tasks(load_annotations(), None, SEED)

    by_image: dict[str, list[str]] = defaultdict(list)
    for t in tasks:
        by_image[t["file_name"]].append(t["truth"])

    totals = Counter(t["truth"] for t in tasks)
    target = {"dev": {c: n * DEV_SHARE for c, n in totals.items()},
              "test": {c: n * (1 - DEV_SHARE) for c, n in totals.items()}}

    # rarest class first: those images have the least room for a bad coin flip
    images = sorted(by_image, key=lambda f: (min(totals[c] for c in by_image[f]), f))
    Random(SEED).shuffle(images)
    images.sort(key=lambda f: min(totals[c] for c in by_image[f]))

    side: dict[str, list[str]] = {"dev": [], "test": []}
    have = {"dev": Counter(), "test": Counter()}

    for name in images:
        labels = by_image[name]
        rarest = min(labels, key=lambda c: totals[c])

        def deficit(s: str) -> tuple:
            # how far this side still is from its quota for the rarest class,
            # then overall, so ties do not all pile onto dev
            return (target[s][rarest] - have[s][rarest],
                    sum(target[s].values()) - sum(have[s].values()))

        pick = max(("dev", "test"), key=deficit)
        side[pick].append(name)
        have[pick].update(labels)

    return {
        "dataset": "fashionpedia instances_attributes_val2020",
        "unit": "image",
        "seed": SEED,
        "dev_share": DEV_SHARE,
        "instances": {s: sum(have[s].values()) for s in have},
        "images": {s: len(side[s]) for s in side},
        "per_class": {s: dict(have[s].most_common()) for s in have},
        "dev": sorted(side["dev"]),
        "test": sorted(side["test"]),
    }


def show(split: dict) -> None:
    print(f"seed {split['seed']}, split by {split['unit']}")
    print(f"  dev   {split['images']['dev']:5} images  {split['instances']['dev']:5} garments")
    print(f"  test  {split['images']['test']:5} images  {split['instances']['test']:5} garments")
    dev, test = split["per_class"]["dev"], split["per_class"]["test"]
    print(f"\n  {'label':10} {'dev':>6} {'test':>6} {'dev share':>10}")
    for label in sorted(set(dev) | set(test), key=lambda c: -(dev.get(c, 0) + test.get(c, 0))):
        d, t = dev.get(label, 0), test.get(label, 0)
        print(f"  {label:10} {d:6} {t:6} {d / (d + t):10.1%}")


def main():
    ap = argparse.ArgumentParser(description="freeze the dev/test split")
    ap.add_argument("--show", action="store_true", help="print the existing split")
    args = ap.parse_args()

    if args.show:
        if not OUT.exists():
            raise SystemExit(f"no split at {OUT} yet, run without --show")
        show(json.loads(OUT.read_text(encoding="utf-8")))
        return

    if OUT.exists():
        raise SystemExit(
            f"{OUT} already exists and is not overwritten.\n"
            "  A split is only meaningful if it never moves. Delete it by hand\n"
            "  if you really mean to, and know that every number measured\n"
            "  against the old one stops being comparable."
        )

    split = build()
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(split, indent=2), encoding="utf-8")
    show(split)
    print(f"\nwritten to {OUT}")


if __name__ == "__main__":
    main()
