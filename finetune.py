"""
finetune.py
Fine-tune the vision tower of a CLIP checkpoint on the category task.

  python finetune.py --epochs 3
  python finetune.py --epochs 3 --limit 4000 --batch-size 32
  python finetune.py --out models/fashionclip-ft --lr 5e-6

The text tower stays frozen and the label prompts stay the ones in config.py, so
the fine-tuned model keeps the zero-shot interface: it is saved with
save_pretrained and evaluate.py reads it back with no changes at all.

  python evaluate.py --model models/fashionclip-ft --split dev

That matters for the comparison. Nothing about the measurement changes between
the zero-shot run and the fine-tuned one except the weights, which is the same
discipline the checkpoint comparison used.

Licensing, stated once and plainly: this trains on Fashionpedia images, which
belong to third parties and are published for research. The resulting weights
are a thesis artifact. They are not shipped, not redistributed, and not what the
product runs; the product stays zero-shot on FashionCLIP, whose MIT weights
someone else trained. Do not blur those two things together.

Needs the training split, which the val-only download skips:

  python scraper.py datasets        # includes train2020.zip, 3.2GB
"""

import argparse
import io
import json
import random
import sys
import time
import zipfile
from collections import Counter
from pathlib import Path

import torch
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from tqdm import tqdm

from config import (
    ATTRIBUTES,
    CATEGORY_ALIASES,
    CLIP_MODEL,
    FASHIONPEDIA_CATEGORY_MAP,
    FASHIONPEDIA_NICKNAME_MAP,
    PROMPT_TEMPLATES,
)
from evaluate import MARGIN, MIN_BOX, crop

TRAIN_ANN = Path("data/fashionpedia/instances_attributes_train2020.json")
TRAIN_ZIP = Path("data/fashionpedia/train2020.zip")

# The model answers with the wide vocabulary and is trained against the ontology
# label the alias folds onto, exactly as at inference time. Training it on the
# twelve while serving it nineteen would teach it a task it is never asked.
VOCABULARY = ATTRIBUTES["category"] + list(CATEGORY_ALIASES)
FOLD = {**{c: c for c in ATTRIBUTES["category"]}, **CATEGORY_ALIASES}
ONTOLOGY = ATTRIBUTES["category"]


def load_train_tasks(limit: int | None, seed: int) -> list[dict]:
    """Same instance selection as the evaluation, on the training split."""
    if not TRAIN_ANN.exists() or not TRAIN_ZIP.exists():
        sys.exit(
            f"missing the Fashionpedia training split.\n"
            f"  need {TRAIN_ANN.name} and {TRAIN_ZIP.name} in data/fashionpedia/\n"
            "  run `python scraper.py datasets` (3.2GB)"
        )

    print(f"reading {TRAIN_ANN.name} ...")
    data = json.loads(TRAIN_ANN.read_text(encoding="utf-8"))
    images = {im["id"]: im["file_name"] for im in data["images"]}
    attr_name = {a["id"]: a["name"] for a in data["attributes"]}

    tasks = []
    for ann in data["annotations"]:
        cat = ann["category_id"]
        if cat not in FASHIONPEDIA_CATEGORY_MAP:
            continue
        truth = FASHIONPEDIA_CATEGORY_MAP[cat]
        for aid in ann.get("attribute_ids", []):
            finer = FASHIONPEDIA_NICKNAME_MAP.get(attr_name.get(aid, ""))
            if finer:
                truth = finer
                break
        if truth is None:
            continue
        x, y, w, h = ann["bbox"]
        if w < MIN_BOX or h < MIN_BOX:
            continue
        tasks.append({"file_name": images[ann["image_id"]],
                      "bbox": (x, y, w, h), "truth": truth})

    rng = random.Random(seed)
    rng.shuffle(tasks)
    if limit:
        tasks = tasks[:limit]
    tasks.sort(key=lambda t: t["file_name"])  # one decode serves several crops
    return tasks


class Crops(Dataset):
    """Garment crops read straight out of the training zip."""

    def __init__(self, tasks: list[dict], processor):
        self.tasks = tasks
        self.processor = processor
        self.zip = None          # opened lazily, per worker
        self.members = None
        self.cache_name = None
        self.cache_img = None

    def __len__(self):
        return len(self.tasks)

    def _open(self):
        if self.zip is None:
            self.zip = zipfile.ZipFile(TRAIN_ZIP)
            self.members = {n.split("/")[-1]: n
                            for n in self.zip.namelist() if n.endswith(".jpg")}

    def __getitem__(self, i):
        self._open()
        t = self.tasks[i]
        if t["file_name"] != self.cache_name:
            with self.zip.open(self.members[t["file_name"]]) as fh:
                self.cache_img = Image.open(io.BytesIO(fh.read())).convert("RGB")
            self.cache_name = t["file_name"]
        piece = crop(self.cache_img, t["bbox"])
        pixels = self.processor(images=piece, return_tensors="pt")["pixel_values"][0]
        return pixels, ONTOLOGY.index(t["truth"])


def text_features(model, processor, device) -> torch.Tensor:
    """
    One frozen vector per vocabulary word, then folded down to the twelve
    ontology labels by averaging the aliases: the training target is an ontology
    label, so the classifier head has to be over those.
    """
    prompts = [PROMPT_TEMPLATES[0].format(w) for w in VOCABULARY]
    with torch.no_grad():
        inputs = processor(text=prompts, return_tensors="pt", padding=True).to(device)
        feats = model.get_text_features(**inputs)
        feats = feats if isinstance(feats, torch.Tensor) else feats.pooler_output
        feats = feats / feats.norm(dim=-1, keepdim=True)

    heads = []
    for label in ONTOLOGY:
        rows = [i for i, w in enumerate(VOCABULARY) if FOLD[w] == label]
        v = feats[rows].mean(dim=0)
        heads.append(v / v.norm())
    return torch.stack(heads)


def accuracy(model, loader, heads, scale, device) -> float:
    model.eval()
    right = total = 0
    with torch.no_grad():
        for pixels, labels in loader:
            pixels, labels = pixels.to(device), labels.to(device)
            img = model.get_image_features(pixel_values=pixels)
            img = img if isinstance(img, torch.Tensor) else img.pooler_output
            img = img / img.norm(dim=-1, keepdim=True)
            pred = (scale * img @ heads.T).argmax(dim=-1)
            right += int((pred == labels).sum())
            total += len(labels)
    model.train()
    return right / total if total else 0.0


def main():
    ap = argparse.ArgumentParser(description="fine-tune CLIP on the category task")
    ap.add_argument("--model", default=CLIP_MODEL, help="checkpoint to start from")
    ap.add_argument("--out", default="models/finetuned", help="where to save")
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--lr", type=float, default=1e-5)
    ap.add_argument("--limit", type=int, help="use only this many training crops")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = ap.parse_args()

    if args.device == "cpu":
        print("no GPU in use: this will be slow enough that --limit is not optional")

    torch.manual_seed(args.seed)
    from transformers import CLIPModel, CLIPProcessor

    print(f"loading {args.model} ...")
    model = CLIPModel.from_pretrained(args.model).to(args.device)
    processor = CLIPProcessor.from_pretrained(args.model)

    # the text tower and the logit scale are frozen: the label prompts do not
    # change, and with a few thousand crops there is nothing to learn there
    for p in model.text_model.parameters():
        p.requires_grad = False
    for p in model.text_projection.parameters():
        p.requires_grad = False
    model.logit_scale.requires_grad = False

    heads = text_features(model, processor, args.device)
    scale = model.logit_scale.exp().detach()

    tasks = load_train_tasks(args.limit, args.seed)
    print(f"{len(tasks)} training crops")
    for label, n in Counter(t["truth"] for t in tasks).most_common():
        print(f"  {label:10} {n}")

    loader = DataLoader(Crops(tasks, processor), batch_size=args.batch_size,
                        shuffle=False, num_workers=args.workers, drop_last=True)

    trainable = [p for p in model.parameters() if p.requires_grad]
    opt = torch.optim.AdamW(trainable, lr=args.lr, weight_decay=0.01)
    steps = args.epochs * (len(tasks) // args.batch_size)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=max(steps, 1))
    loss_fn = torch.nn.CrossEntropyLoss()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    model.train()
    started = time.time()

    for epoch in range(1, args.epochs + 1):
        running, seen = 0.0, 0
        bar = tqdm(loader, desc=f"  epoch {epoch}/{args.epochs}", unit="batch")
        for pixels, labels in bar:
            pixels, labels = pixels.to(args.device), labels.to(args.device)
            img = model.get_image_features(pixel_values=pixels)
            img = img if isinstance(img, torch.Tensor) else img.pooler_output
            img = img / img.norm(dim=-1, keepdim=True)
            loss = loss_fn(scale * img @ heads.T, labels)

            opt.zero_grad()
            loss.backward()
            opt.step()
            sched.step()

            running += float(loss) * len(labels)
            seen += len(labels)
            bar.set_postfix(loss=f"{running / seen:.3f}")

        model.save_pretrained(out)
        processor.save_pretrained(out)
        print(f"  epoch {epoch}: mean loss {running / seen:.4f}, saved to {out}")

    print(f"\ndone in {(time.time() - started) / 60:.1f} min")
    print("measure it against the frozen baseline, on dev and never on test:")
    print(f"  python evaluate.py --model {out} --split dev")


if __name__ == "__main__":
    main()
