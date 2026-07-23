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
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "parola123")

# ----------------------------------------------------------------------------
# CLIP
# ----------------------------------------------------------------------------
CLIP_MODEL = os.getenv("CLIP_MODEL", "openai/clip-vit-base-patch32")

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

# Prompt template used to turn a bare label into a CLIP text query.
# "{}" is filled with the label, e.g. "a photo of a cotton clothing item".
PROMPT_TEMPLATE = "a photo of a {} clothing item"

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
