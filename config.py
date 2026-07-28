"""
config.py
Central configuration: Neo4j credentials, CLIP model, and the label
ontology that CLIP compares each image against (zero-shot).

The ontology covers a whole outfit, not only the garments a cloth segmenter can
cut out. Nine body regions -- upper, lower, full, feet, head, neck, hands,
waist, carried -- and every category is filed under exactly one of them. That is
what lets the wardrobe hold shoes, a beanie, a belt and a bag beside the coat,
and what lets the detector ask a narrow question ("what is on the feet?")
instead of a hopeless one ("what is in this photo?").

Every table here is seeded into Neo4j by `python cli.py seed`, so the knowledge
lives in the graph and can be re-queried, not just imported.
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
# Regions: the nine places a thing can be worn or carried
#
# The region is the spine of the whole ontology. Detection asks about one region
# at a time, the wardrobe is organised by it, the gap analysis counts coverage
# per region, and the classifier's category vocabulary is narrowed to the region
# the segmenter or the band crop already established.
# ----------------------------------------------------------------------------
REGIONS = ["upper", "lower", "full", "feet", "head", "neck", "hands", "waist",
           "carried"]

# Full sentences rather than a shared template: "a photo of a lower clothing
# item" is not English, and the whole point of asking about a region first is
# that its question should be easy to phrase.
REGION_PROMPTS = {
    "upper": "a photo of a garment worn on the upper body",
    "lower": "a photo of a garment worn on the legs and hips",
    "full": "a photo of a one-piece garment covering the whole body",
    "feet": "a photo of something worn on the feet",
    "head": "a photo of something worn on the head or face",
    "neck": "a photo of something worn around the neck",
    "hands": "a photo of something worn on the hands or wrists",
    "waist": "a photo of something worn around the waist",
    "carried": "a photo of a bag someone carries",
}

# What a region is called when a person reads it
REGION_TITLES = {
    "upper": "upper body",
    "lower": "lower body",
    "full": "full length",
    "feet": "feet",
    "head": "head and face",
    "neck": "neck",
    "hands": "hands and wrists",
    "waist": "waist",
    "carried": "carried",
}

# ----------------------------------------------------------------------------
# Kinds: what sort of thing a category is
#
# A coarse grouping above the region, so the graph can answer "show me every
# accessory" without listing thirty names. Region says where it goes; kind says
# what it is.
# ----------------------------------------------------------------------------
KINDS = ["clothing", "footwear", "headwear", "eyewear", "jewellery",
         "accessory", "bag"]

# ----------------------------------------------------------------------------
# Categories: every piece an outfit can be made of
#
# category -> (region, kind, warmth, layer, typical mid-tier price in EUR)
#
# warmth is how much the piece insulates on a 1..5 scale and feeds the warmth
# arithmetic; layer is where it sits in an outfit and drives the recommender's
# slots. One table instead of four parallel dicts, because four parallel dicts
# drift the moment somebody adds a category to three of them.
# ----------------------------------------------------------------------------
CATEGORIES = {
    # ---- upper body ----------------------------------------------------
    "tank top":     ("upper", "clothing", 1, "base",   15),
    "crop top":     ("upper", "clothing", 1, "base",   18),
    "t-shirt":      ("upper", "clothing", 1, "base",   20),
    "polo shirt":   ("upper", "clothing", 2, "base",   30),
    "shirt":        ("upper", "clothing", 2, "base",   35),
    "blouse":       ("upper", "clothing", 2, "base",   40),
    "sweatshirt":   ("upper", "clothing", 3, "mid",    40),
    "cardigan":     ("upper", "clothing", 3, "mid",    50),
    "sweater":      ("upper", "clothing", 4, "mid",    45),
    "hoodie":       ("upper", "clothing", 4, "mid",    45),
    "vest":         ("upper", "clothing", 2, "mid",    35),
    "blazer":       ("upper", "clothing", 3, "mid",    80),
    "raincoat":     ("upper", "clothing", 3, "outer",  90),
    "jacket":       ("upper", "clothing", 4, "outer",  90),
    "puffer jacket": ("upper", "clothing", 5, "outer", 140),
    "coat":         ("upper", "clothing", 5, "outer",  130),
    "parka":        ("upper", "clothing", 5, "outer",  160),

    # ---- lower body ----------------------------------------------------
    "shorts":       ("lower", "clothing", 1, "bottom", 30),
    "skirt":        ("lower", "clothing", 1, "bottom", 40),
    "leggings":     ("lower", "clothing", 2, "bottom", 25),
    "chinos":       ("lower", "clothing", 2, "bottom", 45),
    "trousers":     ("lower", "clothing", 2, "bottom", 50),
    "joggers":      ("lower", "clothing", 3, "bottom", 40),
    "jeans":        ("lower", "clothing", 3, "bottom", 60),

    # ---- one piece -----------------------------------------------------
    "dress":        ("full", "clothing", 2, "full", 60),
    "jumpsuit":     ("full", "clothing", 2, "full", 70),
    "overalls":     ("full", "clothing", 3, "full", 65),
    "suit":         ("full", "clothing", 3, "full", 200),

    # ---- feet ----------------------------------------------------------
    "flip-flops":   ("feet", "footwear", 1, "feet", 12),
    "sandals":      ("feet", "footwear", 1, "feet", 35),
    "socks":        ("feet", "clothing", 2, "feet", 8),
    "loafers":      ("feet", "footwear", 2, "feet", 70),
    "heels":        ("feet", "footwear", 2, "feet", 70),
    "shoes":        ("feet", "footwear", 2, "feet", 70),
    "sneakers":     ("feet", "footwear", 2, "feet", 80),
    "slippers":     ("feet", "footwear", 3, "feet", 20),
    "boots":        ("feet", "footwear", 4, "feet", 110),

    # ---- head and face -------------------------------------------------
    # Eyewear is its own kind, not a subheading of "accessory". A pair of
    # sunglasses is not a belt: it has its own shelf in a shop, its own brands,
    # its own price bracket, and it is the one thing on this list a photograph
    # of a person almost always contains.
    "headband":     ("head", "accessory", 1, "head", 10),
    "earrings":     ("head", "jewellery", 1, "head", 30),
    "sunglasses":   ("head", "eyewear", 1, "head", 40),
    "glasses":      ("head", "eyewear", 1, "head", 90),
    "cap":          ("head", "headwear", 1, "head", 20),
    "hat":          ("head", "headwear", 2, "head", 30),
    "beanie":       ("head", "headwear", 3, "head", 20),

    # ---- neck ----------------------------------------------------------
    "bow tie":      ("neck", "accessory", 1, "neck", 25),
    "tie":          ("neck", "accessory", 1, "neck", 30),
    "necklace":     ("neck", "jewellery", 1, "neck", 35),
    "scarf":        ("neck", "accessory", 3, "neck", 25),

    # ---- hands and wrists ----------------------------------------------
    "ring":         ("hands", "jewellery", 1, "hands", 40),
    "bracelet":     ("hands", "jewellery", 1, "hands", 25),
    "watch":        ("hands", "jewellery", 1, "hands", 120),
    "gloves":       ("hands", "accessory", 3, "hands", 25),

    # ---- waist ---------------------------------------------------------
    "belt":         ("waist", "accessory", 1, "waist", 30),

    # ---- carried -------------------------------------------------------
    "tote bag":     ("carried", "bag", 1, "carried", 25),
    "bag":          ("carried", "bag", 1, "carried", 50),
    "backpack":     ("carried", "bag", 1, "carried", 60),
    "handbag":      ("carried", "bag", 1, "carried", 90),
}

# The flat views the rest of the code and the graph seeder read. Derived, so
# they cannot drift from the table above.
CATEGORY_REGION = {k: v[0] for k, v in CATEGORIES.items()}
CATEGORY_KIND = {k: v[1] for k, v in CATEGORIES.items()}
CATEGORY_WARMTH = {k: (v[2], v[3]) for k, v in CATEGORIES.items()}
CATEGORY_BASE_PRICE = {k: v[4] for k, v in CATEGORIES.items()}
DEFAULT_BASE_PRICE = 40

# Which categories belong to each region, in the table's own order. The
# classifier uses this to narrow its vocabulary once the region is known, which
# is the single biggest accuracy lever now that there are fifty-odd categories:
# choosing between nine kinds of footwear is a far easier question than choosing
# between everything a person can wear.
CATEGORIES_BY_REGION = {
    region: [c for c, r in CATEGORY_REGION.items() if r == region]
    for region in REGIONS
}

# ----------------------------------------------------------------------------
# Things that are not weather
#
# Warmth is added up from material and category, which is right for a coat and
# nonsense for a wristwatch: nobody owns a ring "for cold weather". These
# categories are still stored, still counted, still corrected -- they simply
# claim no season, so the wardrobe never reports itself ready for winter on the
# strength of a bracelet.
# ----------------------------------------------------------------------------
NON_SEASONAL = {
    "ring", "bracelet", "watch", "necklace", "earrings",
    "tie", "bow tie", "belt",
    "sunglasses", "glasses", "headband",
    "bag", "backpack", "handbag", "tote bag",
}


def is_seasonal(category: str | None) -> bool:
    """True when this category's warmth says something about the weather."""
    return bool(category) and category not in NON_SEASONAL


# ----------------------------------------------------------------------------
# Label ontology
# Each group is classified independently: CLIP picks the best label per group.
# ----------------------------------------------------------------------------
ATTRIBUTES = {
    "category": list(CATEGORIES),
    "material": [
        "cotton", "denim", "leather", "suede", "wool", "cashmere", "silk",
        "satin", "linen", "polyester", "nylon", "viscose", "knit", "fleece",
        "down", "faux fur", "corduroy", "velvet", "canvas", "mesh", "rubber",
        "plastic", "metal",
    ],
    "style": [
        "casual", "formal", "business", "sporty", "elegant", "streetwear",
        "vintage", "minimalist", "bohemian", "outdoor",
    ],
    "color": [
        "black", "white", "grey", "blue", "navy", "red", "green", "yellow",
        "orange", "purple", "pink", "brown", "beige", "cream", "gold",
        "silver", "multicoloured",
    ],
    "sleeve": [
        "long sleeves", "short sleeves", "sleeveless",
    ],
    # New group. Pattern is the one visual property CLIP reads well that this
    # ontology had no word for, and it is what separates two otherwise identical
    # shirts in a wardrobe of thirty.
    "pattern": [
        "solid", "striped", "checked", "floral", "printed", "polka dot",
        "animal print", "camouflage", "geometric",
    ],
}

# Which groups are worth asking about for a given region. Asking a pair of
# sneakers about its sleeve length produces a confident answer to a question
# nobody asked, and then stores it.
REGION_GROUPS = {
    "upper": ["category", "material", "style", "color", "sleeve", "pattern"],
    "lower": ["category", "material", "style", "color", "pattern"],
    "full": ["category", "material", "style", "color", "sleeve", "pattern"],
    "feet": ["category", "material", "style", "color", "pattern"],
    "head": ["category", "material", "style", "color", "pattern"],
    "neck": ["category", "material", "style", "color", "pattern"],
    "hands": ["category", "material", "style", "color", "pattern"],
    "waist": ["category", "material", "style", "color", "pattern"],
    "carried": ["category", "material", "style", "color", "pattern"],
}

# Prompt templates used to turn a bare label into a CLIP text query.
# "{}" is filled with the label, e.g. "a photo of a wool sweater".
#
# CLIP is sensitive to phrasing, and the usual remedy is to embed the same label
# under several templates and average the vectors, which cancels the quirks of
# any one sentence. The first entry is also the single-template baseline the
# evaluation compares against, so leave it first.
#
# It used to read "a photo of a {} clothing item", which was fine when the
# ontology was twelve garments and is wrong now that it includes a wristwatch
# and a backpack. The neutral phrasing works for both.
PROMPT_TEMPLATES = [
    "a photo of a {}",
    "a photo of a person wearing a {}",
    "a product photo of a {}",
    "a close-up photo of a {}",
    "a photo of a {} clothing item",
    "a {}",
]
PROMPT_TEMPLATE = PROMPT_TEMPLATES[0]

# ----------------------------------------------------------------------------
# Extra words CLIP may answer with, folded back into the ontology
#
# Most of what used to live here has been promoted to a real category: a blouse
# and a cardigan are things a person owns, not spellings of something else. What
# is left are genuine synonyms, regional variants and plurals -- widening the
# vocabulary CLIP chooses from without widening the graph.
# ----------------------------------------------------------------------------
CATEGORY_ALIASES = {
    "top": "t-shirt",
    "tee": "t-shirt",
    "tshirt": "t-shirt",
    "jumper": "sweater",
    "pullover": "sweater",
    "pants": "trousers",
    "slacks": "trousers",
    "sweatpants": "joggers",
    "tracksuit bottoms": "joggers",
    "tights": "leggings",
    "trainers": "sneakers",
    "running shoes": "sneakers",
    "high heels": "heels",
    "ankle boots": "boots",
    "baseball cap": "cap",
    "woolly hat": "beanie",
    "shades": "sunglasses",
    "spectacles": "glasses",
    "eyeglasses": "glasses",
    "wristwatch": "watch",
    "purse": "handbag",
    "rucksack": "backpack",
    "shoulder bag": "bag",
    "winter coat": "coat",
    "down jacket": "puffer jacket",
    "waistcoat": "vest",
    "gilet": "vest",
}

# ----------------------------------------------------------------------------
# Detection: finding the pieces a cloth segmenter cannot cut out
#
# u2net_cloth_seg returns exactly three masks -- upper, lower, full body. It has
# never seen a shoe. So the pieces it cannot produce are found two other ways,
# both of which reuse the CLIP encoder that is already loaded:
#
#   bands   crop a strip of the photo where a region has to be (above the
#           clothing for the head, below it for the feet) and ask CLIP what is
#           in that strip, offering the region's own categories plus a set of
#           distractors that mean "nothing is here".
#
#   probes  for the things that have no fixed place in the frame -- a belt, a
#           bag, a watch -- ask a yes/no question about the whole photo and take
#           the softmax over the pair.
#
# Both are honest about being weaker than segmentation, which is what the
# thresholds below are for.
# ----------------------------------------------------------------------------

# region -> (anchor, start, height) as fractions of the clothing's own bounding
# box. "above" measures upward from the top of the clothing, "below" downward
# from its bottom, "within" is a slice of the clothing box itself.
DETECTION_BANDS = {
    "head":  ("above", 0.02, 0.34),
    "feet":  ("below", 0.00, 0.30),
    "neck":  ("within", 0.00, 0.16),
    "waist": ("within", 0.42, 0.20),
}

# What a band crop is offered besides the region's categories. If one of these
# wins, the band holds no item and nothing is reported -- which is the answer
# most bands should get.
#
# The last four matter more than they look. A band cut inside the clothing box,
# which is what the waist and neck bands are, is a photograph of clothing by
# construction; offered only "belt" and a set of backgrounds, it will pick belt
# every time, because the crop is certainly not a wall. Giving it a way to say
# "this is just more garment" is what stops a waistband from being reported as
# a belt, and it is what stopped one photograph coming back with its trousers
# counted twice.
BAND_DISTRACTORS = [
    "bare skin",
    "a person's face",
    "hair",
    "a plain background",
    "a wall",
    "the floor",
    "grass",
    "an empty photo",
    "a plain piece of clothing",
    "a shirt",
    "a pair of trousers",
    "fabric",
]

# The accessories with no reliable place in the frame. Asked as a yes/no
# question about the whole photograph.
PROBE_CATEGORIES = [
    "belt", "bag", "backpack", "handbag", "tote bag",
    "watch", "bracelet", "ring", "necklace", "earrings",
    "tie", "bow tie", "scarf", "gloves",
    "sunglasses", "glasses", "cap", "hat", "beanie",
]

PROBE_POSITIVE = "a photo of a person wearing a {}"
PROBE_NEGATIVE = "a photo of a person with no {}"
PROBE_CARRIED_POSITIVE = "a photo of a person carrying a {}"
PROBE_CARRIED_NEGATIVE = "a photo of a person carrying nothing"

# Above FILE it as a garment; between the two, say so in words and file nothing;
# below SPEAK, stay quiet. The gap between them is the whole "if it isn't clear,
# just say so" behaviour: a guess printed as a sentence costs a reader nothing,
# a guess written into the knowledge graph costs them a wrong wardrobe.
DETECT_FILE = 0.55
DETECT_SPEAK = 0.32

# The probes are held to a higher bar than the bands, because they are a weaker
# instrument: a band crop is a picture of one thing and CLIP is being asked what
# it is, whereas a probe is a yes/no about a whole photograph in which the belt
# is forty pixels wide. A binary question also starts at 0.5 rather than at
# 1/n, so the same number does not mean the same thing.
PROBE_FILE = 0.72
PROBE_SPEAK = 0.55

# A band has to be at least this many pixels on its short side to be worth
# cropping; below that there is nothing for CLIP to look at.
MIN_BAND_PX = 48

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
    "mesh": 1,
    "linen": 1,
    "plastic": 1,
    "metal": 1,
    "silk": 2,
    "satin": 2,
    "viscose": 2,
    "cotton": 2,
    "polyester": 2,
    "nylon": 2,
    "canvas": 2,
    "rubber": 2,
    "denim": 3,
    "leather": 3,  # windproof but thin -- a leather jacket is not winter wear
    "suede": 3,
    "corduroy": 3,
    "velvet": 3,
    "knit": 4,
    "fleece": 4,
    "wool": 5,
    "cashmere": 5,
    "down": 5,
    "faux fur": 5,
}

# The layers that sit on the torso, and are therefore the only ones a sleeve
# length says anything about. A pair of jeans, a boot and a wristwatch all have
# a sleeve label if you ask for one, and all three answers are noise.
SLEEVED_LAYERS = {"base", "mid", "outer", "full"}

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

# What a person actually has to put on to leave the house in each season. A
# wardrobe with ten t-shirts and no coat is not ready for winter, and this is
# the table that lets the gap analysis say so: for every season, which body
# regions must be covered and whether an insulating outer layer is required.
# `min_outer_warmth` is the category-warmth an outer piece has to reach to count
# (a jacket is 4, a coat is 5), so a denim jacket does not tick the freezing box.
#
# "feet" is in every list now that footwear is part of the ontology, because
# there is no weather in which shoes are optional. `extras` names the regions
# that stop being decorative once it is genuinely cold.
SEASON_ESSENTIALS = {
    "hot":      {"regions": ["upper", "lower", "feet"], "outer": False,
                 "min_outer_warmth": 0, "extras": []},
    "warm":     {"regions": ["upper", "lower", "feet"], "outer": False,
                 "min_outer_warmth": 0, "extras": []},
    "mild":     {"regions": ["upper", "lower", "feet"], "outer": True,
                 "min_outer_warmth": 4, "extras": []},
    "cold":     {"regions": ["upper", "lower", "feet"], "outer": True,
                 "min_outer_warmth": 4, "extras": ["head", "neck"]},
    "freezing": {"regions": ["upper", "lower", "feet"], "outer": True,
                 "min_outer_warmth": 5, "extras": ["head", "neck", "hands"]},
}

# ----------------------------------------------------------------------------
# Care: when and how to wash, derived from the fibre
#
# The model reads the material off the photo; the care instruction that follows
# from it is knowledge, the same shape as the warmth table. These are the
# conservative version of what a garment's care label would say, and every one
# of them can be overridden per garment by the person who owns the thing and
# knows better than a fibre-name lookup. temp_c is None when the answer is
# "not in a washing machine at all".
# ----------------------------------------------------------------------------
WASH_CARE = {
    "wool":      {"temp_c": 30, "cycle": "wool / hand wash", "note": "reshape and dry flat; heat and agitation felt wool"},
    "cashmere":  {"temp_c": 30, "cycle": "wool / hand wash", "note": "hand wash cold, never wring, dry flat"},
    "silk":      {"temp_c": 30, "cycle": "delicate / hand wash", "note": "mild detergent, do not wring"},
    "satin":     {"temp_c": 30, "cycle": "delicate", "note": "cold and gentle; a hot wash dulls the sheen"},
    "viscose":   {"temp_c": 30, "cycle": "delicate", "note": "weak when wet, so no spinning and no wringing"},
    "linen":     {"temp_c": 40, "cycle": "normal", "note": "wash with like colours, iron while damp"},
    "cotton":    {"temp_c": 40, "cycle": "normal", "note": "colours 30-40, whites tolerate 60"},
    "denim":     {"temp_c": 30, "cycle": "normal, inside out", "note": "cold and inside out keeps the indigo"},
    "corduroy":  {"temp_c": 30, "cycle": "normal, inside out", "note": "inside out protects the pile"},
    "velvet":    {"temp_c": 30, "cycle": "delicate", "note": "do not iron the pile; steam from the back"},
    "leather":   {"temp_c": None, "cycle": "do not machine wash", "note": "wipe clean or specialist leather care only"},
    "suede":     {"temp_c": None, "cycle": "do not machine wash", "note": "brush dry; water marks suede permanently"},
    "faux fur":  {"temp_c": None, "cycle": "do not machine wash", "note": "shake out and spot clean; a machine mats the pile"},
    "down":      {"temp_c": 30, "cycle": "delicate", "note": "tumble low with dryer balls or the down stays clumped"},
    "fleece":    {"temp_c": 30, "cycle": "delicate", "note": "no softener; it clogs the pile and kills the loft"},
    "polyester": {"temp_c": 40, "cycle": "normal", "note": "low heat; synthetics melt on a hot wash or dryer"},
    "nylon":     {"temp_c": 30, "cycle": "delicate", "note": "cool wash, air dry; heat weakens the fibre"},
    "knit":      {"temp_c": 30, "cycle": "delicate", "note": "wash inside out and dry flat to hold the shape"},
    "canvas":    {"temp_c": 30, "cycle": "normal", "note": "air dry; a hot dryer shrinks and stiffens it"},
    "mesh":      {"temp_c": 30, "cycle": "delicate", "note": "use a laundry bag so it does not snag"},
    "rubber":    {"temp_c": None, "cycle": "do not machine wash", "note": "wipe with a damp cloth and air dry"},
    "plastic":   {"temp_c": None, "cycle": "do not machine wash", "note": "wipe clean only"},
    "metal":     {"temp_c": None, "cycle": "do not machine wash", "note": "polish dry; water tarnishes plated metal"},
}

# When the material is unknown or has no entry, this is the answer that will not
# ruin anything: cool and gentle.
DEFAULT_WASH = {"temp_c": 30, "cycle": "delicate",
                "note": "no material was detected; 30 C on a delicate cycle is the safe default"}

# The product is priced and valued in one currency. The user picks it; nothing
# converts, because a wardrobe is not a trading desk.
CURRENCY = os.getenv("CURRENCY", "EUR")
CURRENCY_SYMBOL = {"EUR": "€", "RON": "lei", "USD": "$", "GBP": "£"}.get(CURRENCY, CURRENCY)

# ----------------------------------------------------------------------------
# Brand -> a price estimate
#
# A brand tag is the one cheap signal for what a garment cost, so the upload
# accepts one and the system turns it into a rough figure: a per-category base
# price scaled by the brand's market tier. This is an ESTIMATE and is labelled as
# one everywhere it appears; a real price needs a live product feed, which this
# project does not have and does not pretend to. The owner corrects it in one
# tap, and their number replaces the guess.
#
# The lists are short and Europe-leaning on purpose. An unknown brand is treated
# as mid-range and said to be a guess, rather than refused.
# ----------------------------------------------------------------------------
BRAND_TIERS = {
    "primark": "budget", "shein": "budget", "kik": "budget", "pepco": "budget",
    "c&a": "budget", "lc waikiki": "budget", "sinsay": "budget",
    "h&m": "budget", "hm": "budget",
    "zara": "mid", "mango": "mid", "uniqlo": "mid", "gap": "mid", "next": "mid",
    "bershka": "mid", "pull&bear": "mid", "stradivarius": "mid", "reserved": "mid",
    "s.oliver": "mid", "esprit": "mid", "levi's": "mid", "levis": "mid",
    "nike": "premium", "adidas": "premium", "puma": "premium", "lacoste": "premium",
    "new balance": "premium", "converse": "premium", "vans": "premium",
    "dr. martens": "premium", "timberland": "premium", "birkenstock": "premium",
    "the north face": "premium", "calvin klein": "premium", "tommy hilfiger": "premium",
    "hugo boss": "premium", "boss": "premium", "ralph lauren": "premium",
    "diesel": "premium", "guess": "premium", "superdry": "premium",
    "gucci": "luxury", "prada": "luxury", "burberry": "luxury", "balenciaga": "luxury",
    "louis vuitton": "luxury", "dior": "luxury", "moncler": "luxury", "versace": "luxury",
    "armani": "luxury", "saint laurent": "luxury", "fendi": "luxury", "valentino": "luxury",
    "rolex": "luxury", "omega": "luxury", "cartier": "luxury",
}

# how far each tier moves the base price
TIER_MULTIPLIER = {"budget": 0.55, "mid": 1.0, "premium": 2.2, "luxury": 7.0}

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
# Fashionpedia labels 46 classes. Ids 0-12 are garments and 13-26 are
# accessories and footwear; 27-45 are parts of garments (sleeve, collar, pocket)
# and decorations, which are regions inside another instance and never a whole
# item, so they stay excluded.
#
# Everything from 13 to 25 used to be excluded too, because this ontology had no
# word for a shoe. It has thirty of them now, so the evaluation covers the
# accessory half of the dataset as well: twenty-two of the twenty-seven item
# classes map, against thirteen before.
#
# None still means Fashionpedia knows something this ontology cannot express.
# Those instances are reported separately as coverage, not scored as errors.
# ----------------------------------------------------------------------------
FASHIONPEDIA_CATEGORY_MAP = {
    0: "shirt",      # "shirt, blouse"
    1: "t-shirt",    # "top, t-shirt, sweatshirt" -- one class for three of ours
    2: "sweater",
    3: "cardigan",
    4: "jacket",
    5: "vest",
    6: "trousers",   # "pants" -- Fashionpedia does not split off jeans
    7: "shorts",
    8: "skirt",
    9: "coat",
    10: "dress",
    11: "jumpsuit",
    12: None,        # cape
    13: "glasses",
    14: "hat",
    15: "headband",  # "headband, head covering, hair accessory"
    16: "tie",
    17: "gloves",
    18: "watch",
    19: "belt",
    20: None,        # leg warmer
    21: "leggings",  # "tights, stockings" -- nearest thing this ontology has
    22: "socks",
    23: "shoes",     # generic on both sides, which is why "shoes" exists
    24: "bag",       # "bag, wallet"
    25: "scarf",
    26: None,        # umbrella: carried, but not clothing by any reading
}

# Fashionpedia keeps jeans, hoodie and blazer as "nickname" attributes rather
# than categories, which is exactly where three of our finer labels are hiding.
# When an instance carries one of these, it overrides the category mapping and
# the ground truth becomes the finer label.
FASHIONPEDIA_NICKNAME_MAP = {
    "jeans": "jeans",
    "hoodie": "hoodie",
    "blazer": "blazer",
    "parka": "parka",
    "polo shirt": "polo shirt",
    "tank top": "tank top",
    "crop top": "crop top",
}

# Fashionpedia has no textile fibre attributes at all. Its 294 attributes cover
# silhouette, neckline, length, pattern, opening, waistline, non-textile
# materials (plastic, metal, fur, wood) and 153 style nicknames, but nothing
# that says cotton, wool or denim. The material branch of this pipeline,
# and therefore the warmth score that depends on it, cannot be validated
# against this dataset. Stated here because the evaluation must report it.
FASHIONPEDIA_HAS_FABRIC_LABELS = False

# The ten Fashion-MNIST labels, in Zalando's order (same list as scraper.py),
# mapped onto the categories this project predicts. All ten map now: the four
# that used to dangle -- a sandal, a sneaker, a bag and an ankle boot -- are
# exactly the kinds of thing the expanded ontology was built to hold.
FASHION_MNIST_MAP = {
    "tshirt_top": "t-shirt",
    "trouser": "trousers",
    "pullover": "sweater",
    "dress": "dress",
    "coat": "coat",
    "sandal": "sandals",
    "shirt": "shirt",
    "sneaker": "sneakers",
    "bag": "bag",
    "ankle_boot": "boots",
}


# ----------------------------------------------------------------------------
# Consistency
#
# Every derived table above is built from CATEGORIES, so they cannot disagree.
# What can still disagree is a hand-written set that names a category, and a
# typo there fails silently -- NON_SEASONAL with a misspelled key simply never
# matches, and a wristwatch quietly becomes winter wear. So it is checked at
# import, where it is loud and immediate.
# ----------------------------------------------------------------------------
def _check() -> None:
    unknown = NON_SEASONAL - set(CATEGORIES)
    if unknown:
        raise ValueError(f"NON_SEASONAL names categories that do not exist: {sorted(unknown)}")

    bad_region = {c: r for c, r in CATEGORY_REGION.items() if r not in REGIONS}
    if bad_region:
        raise ValueError(f"categories filed under an unknown region: {bad_region}")

    bad_kind = {c: k for c, k in CATEGORY_KIND.items() if k not in KINDS}
    if bad_kind:
        raise ValueError(f"categories filed under an unknown kind: {bad_kind}")

    collide = set(CATEGORY_ALIASES) & set(CATEGORIES)
    if collide:
        raise ValueError(f"aliases that are also real categories: {sorted(collide)}")

    missing_alias_target = {a: t for a, t in CATEGORY_ALIASES.items() if t not in CATEGORIES}
    if missing_alias_target:
        raise ValueError(f"aliases pointing at nothing: {missing_alias_target}")

    for name, mapping in (("fashionpedia", FASHIONPEDIA_CATEGORY_MAP),
                          ("fashion_mnist", FASHION_MNIST_MAP),
                          ("fashionpedia nicknames", FASHIONPEDIA_NICKNAME_MAP)):
        bad = {k: v for k, v in mapping.items() if v is not None and v not in CATEGORIES}
        if bad:
            raise ValueError(f"{name} map points at unknown categories: {bad}")

    for region, groups in REGION_GROUPS.items():
        if region not in REGIONS:
            raise ValueError(f"REGION_GROUPS names an unknown region: {region}")
        bad = [g for g in groups if g not in ATTRIBUTES]
        if bad:
            raise ValueError(f"REGION_GROUPS[{region}] names unknown groups: {bad}")

    empty = [r for r, cs in CATEGORIES_BY_REGION.items() if not cs]
    if empty:
        raise ValueError(f"regions with no categories in them: {empty}")

    for c in PROBE_CATEGORIES:
        if c not in CATEGORIES:
            raise ValueError(f"PROBE_CATEGORIES names an unknown category: {c}")


_check()
