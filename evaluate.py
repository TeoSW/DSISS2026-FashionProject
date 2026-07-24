"""
evaluate.py
Measure the zero-shot classifier against the Fashionpedia validation split.

  python evaluate.py --limit 200          quick run, 200 instances
  python evaluate.py                      the whole validation split
  python evaluate.py --remove-bg          run rembg on every crop first
  python evaluate.py --json results.json  write the numbers to a file

What is being measured, and what is not:

Fashionpedia annotates every garment in a photo with a bounding box and a
category. Each box is cropped and handed to CLIP on its own, so this scores the
classifier and not the detector: the pipeline never has to find the garment,
it is told where it is. That is the fair comparison, because in the product the
user photographs one item.

Only the category branch can be scored. Fashionpedia's 294 attributes describe
silhouette, neckline, length, pattern and style nicknames, and none of them name
a textile fibre, so there is no ground truth for cotton, wool or denim here.
The predicted materials are printed as a distribution instead, which shows what
the model leans towards but proves nothing about accuracy.

Needs the data first:
  python scraper.py datasets      (or just the val files, see README)
"""

import argparse
import io
import json
import random
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image
from tqdm import tqdm

from config import (
    CATEGORY_REGION,
    CLIP_MODEL,
    FASHIONPEDIA_CATEGORY_MAP,
    FASHIONPEDIA_NICKNAME_MAP,
)

DATA = Path("data/fashionpedia")
ANNOTATIONS = DATA / "instances_attributes_val2020.json"
IMAGES_ZIP = DATA / "val_test2020.zip"

# A box smaller than this is a thumbnail of a sleeve, not a photo of a garment.
MIN_BOX = 48
# Crops are widened slightly: a box cut exactly on the silhouette hides the
# shape of the shoulders and the hem, which is most of what CLIP goes by.
MARGIN = 0.06


def load_annotations() -> dict:
    if not ANNOTATIONS.exists() or not IMAGES_ZIP.exists():
        sys.exit(
            f"missing Fashionpedia data in {DATA}/\n"
            "  need instances_attributes_val2020.json and val_test2020.zip\n"
            "  run `python scraper.py datasets`"
        )
    return json.loads(ANNOTATIONS.read_text(encoding="utf-8"))


def build_tasks(data: dict, limit: int | None, seed: int) -> tuple[list[dict], Counter]:
    """
    One task per garment instance that this ontology can express.

    Returns the tasks and a tally of everything dropped, so the report can say
    what was excluded rather than quietly shrinking the denominator.
    """
    images = {im["id"]: im["file_name"] for im in data["images"]}
    attr_name = {a["id"]: a["name"] for a in data["attributes"]}
    dropped = Counter()

    tasks = []
    for ann in data["annotations"]:
        cat = ann["category_id"]
        if cat not in FASHIONPEDIA_CATEGORY_MAP:
            dropped["not a whole garment (parts, accessories, footwear)"] += 1
            continue

        truth = FASHIONPEDIA_CATEGORY_MAP[cat]
        # a nickname is more specific than the category, so it wins
        for aid in ann.get("attribute_ids", []):
            finer = FASHIONPEDIA_NICKNAME_MAP.get(attr_name.get(aid, ""))
            if finer:
                truth = finer
                break

        if truth is None:
            dropped["garment outside this ontology (vest, jumpsuit, cape)"] += 1
            continue

        x, y, w, h = ann["bbox"]
        if w < MIN_BOX or h < MIN_BOX:
            dropped[f"box smaller than {MIN_BOX}px"] += 1
            continue

        tasks.append({
            "file_name": images[ann["image_id"]],
            "bbox": (x, y, w, h),
            "truth": truth,
        })

    if limit is not None and limit < len(tasks):
        random.Random(seed).shuffle(tasks)
        tasks = tasks[:limit]
    # grouped by photo so that decoding it once covers all its crops
    tasks.sort(key=lambda t: t["file_name"])
    return tasks, dropped


def crop(img: Image.Image, bbox) -> Image.Image:
    x, y, w, h = bbox
    mx, my = w * MARGIN, h * MARGIN
    box = (
        max(0, int(x - mx)), max(0, int(y - my)),
        min(img.width, int(x + w + mx)), min(img.height, int(y + h + my)),
    )
    return img.crop(box)


def run(tasks: list[dict], use_rembg: bool, two_stage: bool, model: str | None,
        ensemble: bool, aliases: bool) -> list[dict]:
    from pipeline import classify

    if model:
        classify.use_model(model)
    classify.use_prompt_ensemble(ensemble)
    classify.use_aliases(aliases)
    if use_rembg:
        from pipeline import remove_bg

    results = []
    with zipfile.ZipFile(IMAGES_ZIP) as z:
        # the archive is one flat folder, so index it once by bare file name
        members = {n.split("/")[-1]: n for n in z.namelist() if n.endswith(".jpg")}
        cache_name, cache_img = None, None

        for task in tqdm(tasks, desc="  classifying", unit="crop"):
            name = task["file_name"]
            if name != cache_name:
                # annotations are grouped by image, so one decode serves several
                # crops of the same photo
                with z.open(members[name]) as fh:
                    cache_img = Image.open(io.BytesIO(fh.read())).convert("RGB")
                cache_name = name

            piece = crop(cache_img, task["bbox"])
            if use_rembg:
                piece = remove_bg.on_white(remove_bg.cut_out(piece))

            if two_stage:
                stage = classify.two_stage_category(piece, mode=two_stage)
                cats = [lbl for lbl, _ in stage["ranked"]]
                row = {
                    "predicted": stage["label"],
                    "confidence": stage["confidence"],
                    "top3": cats[:3],
                    "region": stage["region"],
                    "material": classify.rank(piece, "material")[0][0],
                }
            else:
                ranked = classify.rank_groups(piece, ["category", "material"])
                cats = [lbl for lbl, _ in ranked["category"]]
                row = {
                    "predicted": cats[0],
                    "confidence": round(ranked["category"][0][1], 3),
                    "top3": cats[:3],
                    "material": ranked["material"][0][0],
                }
            results.append({"truth": task["truth"], **row})
    return results


def region_report(results: list[dict]) -> dict | None:
    """
    How much of the two-stage error is the first stage's fault.

    A wrong region cannot be recovered from, so the split between "picked the
    wrong half of the body" and "picked the wrong garment within the right half"
    decides whether the extra stage is worth keeping.
    """
    # the flat classifier commits to a region too, implicitly, through whatever
    # category it named: reporting it makes the two runs comparable
    for r in results:
        r.setdefault("region", CATEGORY_REGION[r["predicted"]])

    right_region = [r for r in results if CATEGORY_REGION[r["truth"]] == r["region"]]
    hit = len(right_region)
    n = len(results)
    within = sum(r["truth"] == r["predicted"] for r in right_region)

    print("\nbody region (implicit in the answer when the run is flat)")
    print(f"  region accuracy     {hit / n:6.1%}   ({hit}/{n})")
    if hit:
        print(f"  category given the right region  {within / hit:6.1%}")

    wrong = Counter(
        (CATEGORY_REGION[r["truth"]], r["region"])
        for r in results if CATEGORY_REGION[r["truth"]] != r["region"]
    )
    for (truth, pred), count in wrong.most_common(5):
        print(f"  {truth:6} read as {pred:6} {count:5}")

    return {
        "region_accuracy": hit / n,
        "category_given_region": within / hit if hit else 0.0,
        "region_confusions": [
            {"truth": t, "predicted": p, "count": c} for (t, p), c in wrong.most_common()
        ],
    }


def report(results: list[dict], dropped: Counter, use_rembg: bool,
           two_stage: bool, model: str, ensemble: bool, aliases: bool) -> dict:
    n = len(results)
    top1 = sum(r["truth"] == r["predicted"] for r in results)
    top3 = sum(r["truth"] in r["top3"] for r in results)

    support = Counter(r["truth"] for r in results)
    correct = Counter(r["truth"] for r in results if r["truth"] == r["predicted"])
    predicted = Counter(r["predicted"] for r in results)
    confusion = Counter(
        (r["truth"], r["predicted"]) for r in results if r["truth"] != r["predicted"]
    )
    # the number to beat: always answer with the commonest class
    baseline = support.most_common(1)[0][1] / n if n else 0

    print(f"\n{n} instances, {model}")
    print(f"  {'two-stage/' + two_stage if two_stage else 'flat'} category, "
          f"{'ensembled' if ensemble else 'single'} prompts, "
          f"aliases {'on' if aliases else 'off'}, "
          f"background removal {'on' if use_rembg else 'off'}")
    print(f"  top-1 accuracy      {top1 / n:6.1%}   ({top1}/{n})")
    print(f"  top-3 accuracy      {top3 / n:6.1%}")
    print(f"  majority baseline   {baseline:6.1%}   (always answer "
          f"'{support.most_common(1)[0][0]}')")
    print(f"  chance              {1 / len(support):6.1%}   ({len(support)} classes)")

    def scores(label: str) -> tuple[float, float, float]:
        rec = correct[label] / support[label]
        prec = correct[label] / predicted[label] if predicted[label] else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        return rec, prec, f1

    print("\nper class")
    print(f"  {'label':10} {'support':>7} {'recall':>7} {'precision':>10} {'F1':>7}")
    for label, sup in support.most_common():
        rec, prec, f1 = scores(label)
        print(f"  {label:10} {sup:7} {rec:7.1%} {prec:10.1%} {f1:7.3f}")

    # unweighted across classes, so hoodie counts as much as dress. Top-1 alone
    # can be carried by the two big classes; this is the number that cannot be.
    per_class = {label: scores(label) for label in support}
    macro_r = sum(v[0] for v in per_class.values()) / len(per_class)
    macro_p = sum(v[1] for v in per_class.values()) / len(per_class)
    macro_f1 = sum(v[2] for v in per_class.values()) / len(per_class)
    print(f"  {'macro':10} {n:7} {macro_r:7.1%} {macro_p:10.1%} {macro_f1:7.3f}")

    never = [lbl for lbl in support if predicted[lbl] == 0]
    if never:
        print(f"  never predicted: {', '.join(sorted(never))}")

    print("\nmost frequent confusions")
    for (truth, pred), count in confusion.most_common(8):
        print(f"  {truth:10} read as {pred:10} {count:5}")

    print("\nmaterials predicted (no ground truth in Fashionpedia)")
    for material, count in Counter(r["material"] for r in results).most_common():
        print(f"  {material:10} {count:5} {count / n:6.1%}")

    if dropped:
        print("\nexcluded from the score")
        for reason, count in dropped.most_common():
            print(f"  {count:6}  {reason}")

    mean_conf = sum(r["confidence"] for r in results) / n if n else 0
    conf_right = [r["confidence"] for r in results if r["truth"] == r["predicted"]]
    conf_wrong = [r["confidence"] for r in results if r["truth"] != r["predicted"]]
    print(f"\nmean confidence     {mean_conf:.3f}")
    if conf_right and conf_wrong:
        print(f"  when correct      {sum(conf_right) / len(conf_right):.3f}")
        print(f"  when wrong        {sum(conf_wrong) / len(conf_wrong):.3f}")

    stages = region_report(results)

    return {
        "instances": n,
        "model": model,
        "prompt_ensemble": ensemble,
        "aliases": aliases,
        "two_stage": two_stage,
        "remove_bg": use_rembg,
        "stages": stages,
        "top1": top1 / n if n else 0,
        "top3": top3 / n if n else 0,
        "majority_baseline": baseline,
        "mean_confidence": mean_conf,
        "macro_recall": macro_r,
        "macro_precision": macro_p,
        "macro_f1": macro_f1,
        "per_class": {
            label: {
                "support": sup,
                "recall": per_class[label][0],
                "precision": per_class[label][1],
                "f1": per_class[label][2],
            }
            for label, sup in support.most_common()
        },
        "confusions": [
            {"truth": t, "predicted": p, "count": c} for (t, p), c in confusion.most_common(20)
        ],
        "materials_predicted": dict(Counter(r["material"] for r in results).most_common()),
        "excluded": dict(dropped),
    }


def main():
    ap = argparse.ArgumentParser(description="CLIP vs Fashionpedia")
    ap.add_argument("--limit", type=int, help="evaluate a random subset of this size")
    ap.add_argument("--seed", type=int, default=0, help="subset seed, for repeatable runs")
    ap.add_argument("--remove-bg", action="store_true",
                    help="run rembg on each crop, as the CLI pipeline does")
    ap.add_argument("--two-stage", choices=["prompt", "mass"], default=None,
                    help="pick the body region first, then the category in it; "
                         "'prompt' asks CLIP for the region, 'mass' adds up the "
                         "category probabilities already falling in each region")
    ap.add_argument("--model", help=f"CLIP checkpoint to use (default {CLIP_MODEL})")
    ap.add_argument("--prompt-ensemble", action="store_true",
                    help="average every label over all PROMPT_TEMPLATES")
    ap.add_argument("--no-aliases", action="store_true",
                    help="offer CLIP only the 12 ontology labels, no CATEGORY_ALIASES")
    ap.add_argument("--json", help="write the numbers to this file")
    args = ap.parse_args()

    data = load_annotations()
    tasks, dropped = build_tasks(data, args.limit, args.seed)
    print(f"{len(tasks)} garment instances to classify")

    results = run(tasks, args.remove_bg, args.two_stage, args.model,
                  args.prompt_ensemble, not args.no_aliases)
    summary = report(results, dropped, args.remove_bg, args.two_stage,
                     args.model or CLIP_MODEL, args.prompt_ensemble,
                     not args.no_aliases)

    if args.json:
        Path(args.json).write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"\nwritten to {args.json}")


if __name__ == "__main__":
    main()
