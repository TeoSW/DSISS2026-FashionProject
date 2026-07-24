"""
clothing_scraper.py
Config-driven scraper for building a clothing image dataset.

Three modes:
  1. datasets      - pull established open datasets (Fashionpedia) with direct downloads
  2. fashion-mnist - pull Zalando's Fashion-MNIST from Kaggle (needs an API key)
  3. scrape        - crawl product listing pages you define in SOURCES, download
                     images + metadata into a training-ready folder structure

Output layout:
  data/
    raw/<source>/<category>/img_000123.jpg
    fashion_mnist/images/<split>/<class>/00042.png
    metadata.jsonl          (one record per image)
    seen_hashes.txt         (dedup state, safe to resume)

Usage:
  python clothing_scraper.py datasets
  python clothing_scraper.py fashion-mnist --export
  python clothing_scraper.py scrape --source example_shop --max-per-category 200
  python clothing_scraper.py scrape --all

Requires: pip install requests beautifulsoup4 pillow tqdm
"""

import argparse
import csv
import hashlib
import io
import json
import os
import random
import sys
import time
import urllib.robotparser
import zipfile
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from PIL import Image
from tqdm import tqdm

# ----------------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------------

DATA_DIR = Path("data")
RAW_DIR = DATA_DIR / "raw"
META_FILE = DATA_DIR / "metadata.jsonl"
HASH_FILE = DATA_DIR / "seen_hashes.txt"

MIN_WIDTH = 400          # discard thumbnails
MIN_HEIGHT = 400
DELAY_RANGE = (1.5, 4.0)  # seconds between requests, randomized
TIMEOUT = 20
MAX_RETRIES = 3

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# Each source defines how to walk listing pages and where to find data.
# Fill these in per target site after inspecting its HTML (DevTools > Elements).
# The selectors below are placeholders showing the expected structure.
SOURCES = {
    "example_shop": {
        "base_url": "https://www.example-shop.com",
        # category name -> listing URL (use {page} for pagination)
        "categories": {
            "tshirt": "/en/men/t-shirts?page={page}",
            "jeans": "/en/men/jeans?page={page}",
            "jacket": "/en/men/jackets?page={page}",
            "dress": "/en/women/dresses?page={page}",
        },
        "max_pages": 10,
        # CSS selector for product cards on the listing page
        "card_selector": "article.product-card",
        # relative to card: link to product page (optional, set None to skip)
        "link_selector": "a",
        # relative to card: the <img> tag
        "img_selector": "img",
        # which attribute holds the real image URL (src, data-src, srcset...)
        "img_attr": "data-src",
        # relative to card: product title
        "title_selector": ".product-card__title",
        # relative to card: price (optional)
        "price_selector": ".product-card__price",
    },
    # Add more sources here with the same structure.
}

# Zalando's Fashion-MNIST, hosted on Kaggle.
# 70k images, 28x28, grayscale, 10 classes. No material, no colour, no texture:
# useful as a sanity check / baseline, not as a source of the attributes this
# project actually predicts.
KAGGLE_DATASET = "zalando-research/fashionmnist"
KAGGLE_API = "https://www.kaggle.com/api/v1/datasets/download"

# label id -> folder name, in the order Zalando defined them
FASHION_MNIST_CLASSES = [
    "tshirt_top", "trouser", "pullover", "dress", "coat",
    "sandal", "shirt", "sneaker", "bag", "ankle_boot",
]

FASHION_MNIST_CSV = {
    "train": "fashion-mnist_train.csv",
    "test": "fashion-mnist_test.csv",
}

FASHIONPEDIA_FILES = {
    "instances_attributes_train2020.json": "https://s3.amazonaws.com/ifashionist-dataset/annotations/instances_attributes_train2020.json",
    "instances_attributes_val2020.json": "https://s3.amazonaws.com/ifashionist-dataset/annotations/instances_attributes_val2020.json",
    "train2020.zip": "https://s3.amazonaws.com/ifashionist-dataset/images/train2020.zip",
    "val_test2020.zip": "https://s3.amazonaws.com/ifashionist-dataset/images/val_test2020.zip",
}

# evaluate.py only reads these two, 240MB against the 3.4GB of the full set.
# The training split is only worth downloading for fine-tuning, which this
# project does not do on Fashionpedia images.
FASHIONPEDIA_VAL_FILES = ["instances_attributes_val2020.json", "val_test2020.zip"]

# ----------------------------------------------------------------------------
# HELPERS
# ----------------------------------------------------------------------------

session = requests.Session()
session.headers.update(HEADERS)


def polite_sleep():
    time.sleep(random.uniform(*DELAY_RANGE))


def robots_allows(base_url: str, path: str) -> bool:
    """Check robots.txt once per host and cache the parser."""
    host = urlparse(base_url).netloc
    if host not in robots_allows._cache:
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(urljoin(base_url, "/robots.txt"))
        try:
            rp.read()
        except Exception:
            rp = None  # unreachable robots.txt: proceed but stay polite
        robots_allows._cache[host] = rp
    rp = robots_allows._cache[host]
    if rp is None:
        return True
    return rp.can_fetch(HEADERS["User-Agent"], urljoin(base_url, path))


robots_allows._cache = {}


def fetch(url: str) -> requests.Response | None:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = session.get(url, timeout=TIMEOUT)
            if r.status_code == 200:
                return r
            if r.status_code in (403, 429):
                wait = 30 * attempt
                print(f"  [{r.status_code}] backing off {wait}s: {url}")
                time.sleep(wait)
            else:
                return None
        except requests.RequestException as e:
            print(f"  request failed ({e}), retry {attempt}/{MAX_RETRIES}")
            time.sleep(5 * attempt)
    return None


def load_seen_hashes() -> set[str]:
    if HASH_FILE.exists():
        return set(HASH_FILE.read_text().split())
    return set()


def append_hash(h: str):
    with HASH_FILE.open("a") as f:
        f.write(h + "\n")


def append_metadata(record: dict):
    with META_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def clean_img_url(url: str, base_url: str) -> str | None:
    if not url:
        return None
    # srcset: take the largest candidate
    if "," in url and " " in url:
        candidates = [c.strip().split(" ")[0] for c in url.split(",")]
        url = candidates[-1]
    url = url.strip()
    if url.startswith("//"):
        url = "https:" + url
    elif url.startswith("/"):
        url = urljoin(base_url, url)
    if not url.startswith("http"):
        return None
    return url


def save_image(content: bytes, dest: Path) -> tuple[bool, str]:
    """Validate, filter by resolution, convert to RGB JPEG. Returns (ok, reason)."""
    try:
        img = Image.open(io.BytesIO(content))
        img.verify()
        img = Image.open(io.BytesIO(content))  # reopen after verify
    except Exception:
        return False, "not_an_image"
    if img.width < MIN_WIDTH or img.height < MIN_HEIGHT:
        return False, f"too_small_{img.width}x{img.height}"
    img.convert("RGB").save(dest, "JPEG", quality=92)
    return True, "ok"


# ----------------------------------------------------------------------------
# SCRAPE MODE
# ----------------------------------------------------------------------------

def scrape_source(source_name: str, max_per_category: int):
    cfg = SOURCES[source_name]
    base = cfg["base_url"]
    seen = load_seen_hashes()
    counter = 0

    for category, url_tpl in cfg["categories"].items():
        out_dir = RAW_DIR / source_name / category
        out_dir.mkdir(parents=True, exist_ok=True)
        saved = 0
        print(f"\n[{source_name}] category: {category}")

        for page in range(1, cfg["max_pages"] + 1):
            if saved >= max_per_category:
                break
            path = url_tpl.format(page=page)
            if not robots_allows(base, path):
                print(f"  robots.txt disallows {path}, skipping category")
                break

            resp = fetch(urljoin(base, path))
            polite_sleep()
            if resp is None:
                print(f"  page {page}: fetch failed, stopping category")
                break

            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.select(cfg["card_selector"])
            if not cards:
                print(f"  page {page}: no product cards found, stopping")
                break

            for card in tqdm(cards, desc=f"  page {page}", leave=False):
                if saved >= max_per_category:
                    break

                img_tag = card.select_one(cfg["img_selector"])
                if img_tag is None:
                    continue
                img_url = clean_img_url(
                    img_tag.get(cfg["img_attr"]) or img_tag.get("src"), base
                )
                if img_url is None:
                    continue

                title_tag = card.select_one(cfg["title_selector"])
                title = title_tag.get_text(strip=True) if title_tag else ""
                price = ""
                if cfg.get("price_selector"):
                    price_tag = card.select_one(cfg["price_selector"])
                    price = price_tag.get_text(strip=True) if price_tag else ""
                link = ""
                if cfg.get("link_selector"):
                    a = card.select_one(cfg["link_selector"])
                    if a and a.get("href"):
                        link = urljoin(base, a["href"])

                img_resp = fetch(img_url)
                polite_sleep()
                if img_resp is None:
                    continue

                h = hashlib.md5(img_resp.content).hexdigest()
                if h in seen:
                    continue

                dest = out_dir / f"img_{h[:12]}.jpg"
                ok, reason = save_image(img_resp.content, dest)
                if not ok:
                    continue

                seen.add(h)
                append_hash(h)
                append_metadata({
                    "source": source_name,
                    "category": category,
                    "title": title,
                    "price": price,
                    "product_url": link,
                    "image_url": img_url,
                    "local_path": str(dest),
                    "md5": h,
                    "scraped_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                })
                saved += 1
                counter += 1

        print(f"  saved {saved} images for '{category}'")

    print(f"\nDone. {counter} new images from '{source_name}'.")
    print(f"Metadata: {META_FILE}")


# ----------------------------------------------------------------------------
# DATASETS MODE (Fashionpedia direct download)
# ----------------------------------------------------------------------------

def download_datasets(val_only: bool = False):
    out = DATA_DIR / "fashionpedia"
    out.mkdir(parents=True, exist_ok=True)
    wanted = FASHIONPEDIA_VAL_FILES if val_only else FASHIONPEDIA_FILES
    for fname in wanted:
        url = FASHIONPEDIA_FILES[fname]
        dest = out / fname
        if dest.exists():
            print(f"exists, skipping: {fname}")
            continue
        print(f"downloading {fname} ...")
        # .part first, and resumed on retry: these are large files and the
        # connection drops often enough that restarting from zero is painful
        part = dest.with_suffix(dest.suffix + ".part")
        for attempt in range(1, MAX_RETRIES + 1):
            have = part.stat().st_size if part.exists() else 0
            headers = {"Range": f"bytes={have}-"} if have else {}
            try:
                with session.get(url, headers=headers, stream=True, timeout=TIMEOUT) as r:
                    if r.status_code not in (200, 206):
                        print(f"  failed ({r.status_code}): {url}")
                        break
                    if r.status_code == 200:
                        have = 0  # server ignored the range, start over
                    total = have + int(r.headers.get("content-length", 0))
                    with part.open("ab" if have else "wb") as f, tqdm(
                        total=total, initial=have, unit="B", unit_scale=True,
                        desc=f"  {fname}"
                    ) as bar:
                        for chunk in r.iter_content(chunk_size=1 << 20):
                            f.write(chunk)
                            have += len(chunk)
                            bar.update(len(chunk))
                if total and have >= total:
                    part.replace(dest)
                    break
                print(f"  truncated at {have}/{total}, resuming")
            except requests.RequestException as e:
                print(f"  {e}, retry {attempt}/{MAX_RETRIES}")
                time.sleep(5 * attempt)
        else:
            print(f"  gave up on {fname}")
    print("\nUnzip the image archives, then annotations are COCO-format JSON.")
    print("DeepFashion2 needs a signed request form (Google Form on its GitHub"
          " repo, github.com/switchablenorms/DeepFashion2), so it can't be"
          " auto-downloaded here.")


# ----------------------------------------------------------------------------
# FASHION-MNIST MODE (Kaggle, needs credentials)
# ----------------------------------------------------------------------------

def kaggle_credentials() -> tuple[str, str]:
    """
    Resolve Kaggle API credentials, in the order the official client uses:
      1. KAGGLE_USERNAME / KAGGLE_KEY environment variables
      2. kaggle.json in $KAGGLE_CONFIG_DIR or ~/.kaggle
    Get the file from kaggle.com > your profile > Settings > Create New Token.
    """
    user, key = os.getenv("KAGGLE_USERNAME"), os.getenv("KAGGLE_KEY")
    if user and key:
        return user, key

    config_dir = Path(os.getenv("KAGGLE_CONFIG_DIR", Path.home() / ".kaggle"))
    cred_file = config_dir / "kaggle.json"
    if cred_file.exists():
        data = json.loads(cred_file.read_text(encoding="utf-8"))
        if data.get("username") and data.get("key"):
            return data["username"], data["key"]

    raise SystemExit(
        "No Kaggle credentials found.\n"
        "  1. kaggle.com > profile picture > Settings > API > Create New Token\n"
        f"  2. drop the downloaded kaggle.json in {config_dir}\n"
        "  (or set KAGGLE_USERNAME and KAGGLE_KEY instead)"
    )


def download_fashion_mnist() -> Path:
    """Download and unzip the Kaggle archive. Returns the extraction folder."""
    out = DATA_DIR / "fashion_mnist"
    out.mkdir(parents=True, exist_ok=True)
    zip_path = out / "fashionmnist.zip"

    if not zip_path.exists():
        auth = kaggle_credentials()
        url = f"{KAGGLE_API}/{KAGGLE_DATASET}"
        print(f"downloading {KAGGLE_DATASET} from Kaggle ...")
        with requests.get(url, auth=auth, stream=True, timeout=TIMEOUT) as r:
            if r.status_code == 401:
                raise SystemExit("Kaggle rejected the credentials (401).")
            if r.status_code == 403:
                raise SystemExit(
                    "Kaggle returned 403. Open "
                    f"https://www.kaggle.com/datasets/{KAGGLE_DATASET} once in a "
                    "browser and accept the dataset rules, then retry."
                )
            if r.status_code != 200:
                raise SystemExit(f"Kaggle download failed ({r.status_code}).")
            total = int(r.headers.get("content-length", 0))
            # .part first, so an interrupted download is not mistaken for a good one
            part = zip_path.with_suffix(".part")
            with part.open("wb") as f, tqdm(
                total=total, unit="B", unit_scale=True, desc="  fashionmnist.zip"
            ) as bar:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
                    bar.update(len(chunk))
            part.replace(zip_path)
    else:
        print(f"exists, skipping download: {zip_path}")

    with zipfile.ZipFile(zip_path) as z:
        z.extractall(out)
    print(f"extracted to {out}")
    return out


def export_fashion_mnist_images(split: str, limit: int | None, size: int) -> None:
    """
    Turn the pixel CSV into real PNG files, one folder per class, so the images
    go through the same pipeline as any photo.

    Each CSV row is: label, pixel1 ... pixel784 (0-255, row-major 28x28).
    """
    src = DATA_DIR / "fashion_mnist" / FASHION_MNIST_CSV[split]
    if not src.exists():
        raise SystemExit(f"missing {src} -- run `python scraper.py fashion-mnist` first")

    out_root = DATA_DIR / "fashion_mnist" / "images" / split
    for name in FASHION_MNIST_CLASSES:
        (out_root / name).mkdir(parents=True, exist_ok=True)

    per_class = {i: 0 for i in range(len(FASHION_MNIST_CLASSES))}
    written = 0

    with src.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)  # header
        for row in tqdm(reader, desc=f"  {split}", unit="img"):
            label = int(row[0])
            if limit is not None and per_class[label] >= limit:
                if all(c >= limit for c in per_class.values()):
                    break
                continue

            img = Image.frombytes("L", (28, 28), bytes(int(p) for p in row[1:785]))
            if size != 28:
                # upscaled with LANCZOS; CLIP wants 224px input, but nothing
                # creates detail that was never in a 28x28 thumbnail
                img = img.resize((size, size), Image.LANCZOS)

            folder = out_root / FASHION_MNIST_CLASSES[label]
            img.save(folder / f"{per_class[label]:05d}.png")
            per_class[label] += 1
            written += 1

    print(f"wrote {written} PNGs to {out_root}")
    for i, name in enumerate(FASHION_MNIST_CLASSES):
        print(f"  {name:12} {per_class[i]}")


# ----------------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Clothing dataset builder")
    sub = parser.add_subparsers(dest="mode", required=True)

    ds = sub.add_parser("datasets", help="download Fashionpedia")
    ds.add_argument("--val-only", action="store_true",
                    help="skip the 3.2GB training split, enough for evaluate.py")

    fm = sub.add_parser("fashion-mnist", help="download Zalando Fashion-MNIST from Kaggle")
    fm.add_argument("--export", action="store_true", help="also write PNG images")
    fm.add_argument("--split", choices=["train", "test", "both"], default="both")
    fm.add_argument("--limit", type=int, help="max images per class (default: all)")
    fm.add_argument("--size", type=int, default=28, help="output size, e.g. 224 for CLIP")

    sp = sub.add_parser("scrape", help="scrape configured sources")
    sp.add_argument("--source", choices=list(SOURCES), help="single source")
    sp.add_argument("--all", action="store_true", help="scrape every source")
    sp.add_argument("--max-per-category", type=int, default=300)

    args = parser.parse_args()
    DATA_DIR.mkdir(exist_ok=True)

    if args.mode == "datasets":
        download_datasets(args.val_only)
    elif args.mode == "fashion-mnist":
        download_fashion_mnist()
        if args.export:
            splits = ["train", "test"] if args.split == "both" else [args.split]
            for split in splits:
                export_fashion_mnist_images(split, args.limit, args.size)
    else:
        if not args.source and not args.all:
            print("Pick --source NAME or --all")
            sys.exit(1)
        targets = list(SOURCES) if args.all else [args.source]
        for s in targets:
            scrape_source(s, args.max_per_category)


if __name__ == "__main__":
    main()