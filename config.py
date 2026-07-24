"""
config.py
Central configuration: Neo4j credentials, CLIP model, and the label
ontology that CLIP compares each image against (zero-shot).

The label lists are a small, editable subset inspired by the Fashionpedia
ontology (27 categories, 294 fine-grained attributes). Start small, expand
as you see what CLIP handles well.
"""

import os

from dotenv import load_dotenv

load_dotenv()  # reads .env if present

# ----------------------------------------------------------------------------
# Neo4j
# ----------------------------------------------------------------------------
# The real password lives in .env, which is gitignored. The fallbacks below are
# throwaway defaults for a fresh clone, not the credentials this project runs on.
# Neo4j Community has exactly one account, the built-in "neo4j": multiple users
# and CREATE USER are Enterprise features, so the name is not configurable.
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "parola123")

# ----------------------------------------------------------------------------
# CLIP
# ----------------------------------------------------------------------------
# FashionCLIP is OpenAI's CLIP further trained on 800K fashion product pairs,
# released under MIT. On the Fashionpedia validation split it beats the plain
# ViT-B/32 by 10.4 points and the three times larger ViT-L/14 by more, which is
# the whole argument for it: on this task the domain matters and the size does
# not. Set CLIP_MODEL in .env to compare against any other checkpoint.
CLIP_MODEL = os.getenv("CLIP_MODEL", "patrickjohncyh/fashion-clip")

# ----------------------------------------------------------------------------
# Label ontology
# Each group is classified independently: CLIP picks the best label per group.
# ----------------------------------------------------------------------------
ATTRIBUTES = {
    "category": [
        "t-shirt", "shirt", "sweater", "jacket", "coat", "dress",
        "skirt", "jeans", "trousers", "shorts", "hoodie", "blazer",
    ],
    "material": [
        "cotton", "denim", "leather", "wool", "silk",
        "linen", "polyester", "knit",
    ],
    "style": [
        "casual", "formal", "sporty", "elegant", "streetwear", "vintage",
    ],
    "color": [
        "black", "white", "grey", "blue", "red", "green",
        "yellow", "brown", "beige", "pink",
    ],
    "sleeve": [
        "long sleeves", "short sleeves", "sleeveless",
    ],
}

# Prompt templates used to turn a bare label into a CLIP text query.
# "{}" is filled with the label, e.g. "a photo of a cotton clothing item".
#
# CLIP is sensitive to phrasing, and the usual remedy is to embed the same label
# under several templates and average the vectors, which cancels the quirks of
# any one sentence. The first entry is also the single-template baseline the
# evaluation compares against, so leave it first.
PROMPT_TEMPLATES = [
    "a photo of a {} clothing item",
    "a photo of a {}",
    "a photo of a person wearing a {}",
    "a product photo of a {}",
    "a close-up photo of a {}",
    "a {}",
]
PROMPT_TEMPLATE = PROMPT_TEMPLATES[0]

# ----------------------------------------------------------------------------
# Extra words CLIP may answer with, folded back into the ontology
#
# The ontology has twelve categories because the warmth tables and the graph are
# built on twelve. That does not mean CLIP has to be offered only twelve words.
# Its largest error is reading a top as a dress, a shirt or a sweater, and one
# plausible cause is that a tank top has nowhere to go: forced to choose, the
# model picks whatever else is close.
#
# So the vocabulary is widened and the answer is folded back afterwards. The
# graph never sees these words, only the twelve on the right-hand side.
# ----------------------------------------------------------------------------
CATEGORY_ALIASES = {
    "top": "t-shirt",
    "tank top": "t-shirt",
    "crop top": "t-shirt",
    "blouse": "shirt",
    "polo shirt": "shirt",
    "sweatshirt": "sweater",
    "cardigan": "sweater",
}

# ----------------------------------------------------------------------------
# Two-stage classification
#
# The flat classifier's largest error group is not subtle: it reads tops as
# skirts and shorts, confusing garments worn on opposite halves of the body.
# So ask the easier question first, which part of the body this covers, and
# then choose only among the categories that live there.
#
# The region of a garment is derived from this table and not from Fashionpedia's
# own supercategories, which file a coat under "wholebody" while this ontology
# treats it as an upper layer.
# ----------------------------------------------------------------------------
CATEGORY_REGION = {
    "t-shirt": "upper",
    "shirt": "upper",
    "sweater": "upper",
    "hoodie": "upper",
    "blazer": "upper",
    "jacket": "upper",
    "coat": "upper",
    "trousers": "lower",
    "jeans": "lower",
    "skirt": "lower",
    "shorts": "lower",
    "dress": "full",
}

# Full sentences rather than a shared template: "a photo of a lower clothing
# item" is not English, and the whole point of the first stage is that its
# question should be easy to phrase.
REGION_PROMPTS = {
    "upper": "a photo of a garment worn on the upper body",
    "lower": "a photo of a garment worn on the legs and hips",
    "full": "a photo of a one-piece garment covering the whole body",
}

# ----------------------------------------------------------------------------
# Warmth ontology -> the part CLIP cannot see
#
# Weather suitability is not a visual property, it is knowledge about the
# garment. We give every material and every category a warmth weight (1 = cools
# you down, 5 = keeps you warm), add the two, adjust for sleeves, and match the
# result against the Season nodes below. These numbers are seeded into Neo4j by
# `python cli.py seed`, so the reasoning lives in the graph, not in the model.
# ----------------------------------------------------------------------------
MATERIAL_WARMTH = {
    "linen": 1,
    "silk": 2,
    "cotton": 2,
    "polyester": 2,
    "denim": 3,
    "leather": 3,  # windproof but thin -- a leather jacket is not winter wear
    "knit": 4,
    "wool": 5,
}

# warmth = how much it insulates, layer = where it sits in an outfit
CATEGORY_WARMTH = {
    "t-shirt": (1, "base"),
    "shorts": (1, "bottom"),
    "skirt": (1, "bottom"),
    "dress": (2, "full"),
    "shirt": (2, "base"),
    "trousers": (2, "bottom"),
    "jeans": (3, "bottom"),
    "blazer": (3, "mid"),
    "hoodie": (4, "mid"),
    "sweater": (4, "mid"),
    "jacket": (4, "outer"),
    "coat": (5, "outer"),
}

SLEEVE_MODIFIER = {
    "sleeveless": -1,
    "short sleeves": 0,
    "long sleeves": 1,
}

# Overlapping windows on the 1..11 warmth scale, on purpose: a denim jacket
# honestly belongs to both "mild" and "cold".
SEASONS = [
    {"name": "hot",      "temp_range": "above 25 C", "warmth_min": 1, "warmth_max": 3},
    {"name": "warm",     "temp_range": "18-25 C",    "warmth_min": 3, "warmth_max": 5},
    {"name": "mild",     "temp_range": "10-18 C",    "warmth_min": 5, "warmth_max": 8},
    {"name": "cold",     "temp_range": "0-10 C",     "warmth_min": 7, "warmth_max": 10},
    {"name": "freezing", "temp_range": "below 0 C",  "warmth_min": 10, "warmth_max": 11},
]

# ----------------------------------------------------------------------------
# Dataset provenance -> the licensing story, expressed as data
#
# scraper.py can fetch three kinds of images, and they do NOT carry the same
# rights. Putting that in the graph means a garment can always be traced back to
# where its picture came from and what may legally be done with it, instead of
# the answer living in a paragraph of the README.
# ----------------------------------------------------------------------------
DATASETS = [
    {
        "name": "fashion_mnist",
        "title": "Fashion-MNIST (Zalando Research)",
        "license": "MIT",
        "usage": "training and commercial use allowed",
        "source": "kaggle:zalando-research/fashionmnist",
        "images": 70000,
        "note": "28x28 grayscale: category only, no material/colour/texture",
    },
    {
        "name": "fashionpedia",
        "title": "Fashionpedia (Jia et al., 2020)",
        "license": "annotations CC-BY-4.0; images owned by third parties",
        "usage": "evaluation and research only, never redistributed",
        "source": "https://s3.amazonaws.com/ifashionist-dataset/",
        "images": 48825,
        "note": "27 categories, 294 fine-grained attributes -- the eval target",
    },
    {
        "name": "scraped",
        "title": "Product listings crawled by scraper.py",
        "license": "unknown, per-site terms of service",
        "usage": "inspection only; robots.txt is not a licence",
        "source": "SOURCES in scraper.py",
        "images": 0,
        "note": "whoever points the scraper at a site owns that decision",
    },
]

# ----------------------------------------------------------------------------
# Fashionpedia -> this project's ontology
#
# Fashionpedia labels 46 classes. Only ids 0-12 are garments; 13-26 are
# accessories and footwear, 27-45 are parts of garments (sleeve, collar, pocket)
# and decorations, which are regions inside another instance and never a whole
# item. Everything outside 0-12 is excluded from the evaluation rather than
# counted as a miss: the pipeline was never asked to name a zipper.
#
# None means Fashionpedia knows a garment this ontology cannot express. Those
# instances are reported separately as coverage, not scored as errors.
# ----------------------------------------------------------------------------
FASHIONPEDIA_CATEGORY_MAP = {
    0: "shirt",      # "shirt, blouse"
    1: "t-shirt",    # "top, t-shirt, sweatshirt" -- one class for three of ours
    2: "sweater",
    3: "sweater",    # cardigan: no separate label here, same layer and warmth
    4: "jacket",
    5: None,         # vest
    6: "trousers",   # "pants" -- Fashionpedia does not split off jeans
    7: "shorts",
    8: "skirt",
    9: "coat",
    10: "dress",
    11: None,        # jumpsuit
    12: None,        # cape
}

# Fashionpedia keeps jeans, hoodie and blazer as "nickname" attributes rather
# than categories, which is exactly where the three labels missing from the map
# above are hiding. When an instance carries one of these, it overrides the
# category mapping and the ground truth becomes the finer label.
FASHIONPEDIA_NICKNAME_MAP = {
    "jeans": "jeans",
    "hoodie": "hoodie",
    "blazer": "blazer",
}

# Fashionpedia has no textile fibre attributes at all. Its 294 attributes cover
# silhouette, neckline, length, pattern, opening, waistline, non-textile
# materials (plastic, metal, fur, wood) and 153 style nicknames, but nothing
# that says cotton, wool or denim. The material branch of this pipeline,
# and therefore the warmth score that depends on it, cannot be validated
# against this dataset. Stated here because the evaluation must report it.
FASHIONPEDIA_HAS_FABRIC_LABELS = False

# The ten Fashion-MNIST labels, in Zalando's order (same list as scraper.py),
# mapped onto the categories this project predicts. None = outside our ontology,
# which is exactly the gap the evaluation script has to report.
FASHION_MNIST_MAP = {
    "tshirt_top": "t-shirt",
    "trouser": "trousers",
    "pullover": "sweater",
    "dress": "dress",
    "coat": "coat",
    "sandal": None,      # footwear: not in ATTRIBUTES["category"]
    "shirt": "shirt",
    "sneaker": None,     # footwear
    "bag": None,         # accessory
    "ankle_boot": None,  # footwear
}
