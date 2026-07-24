"""
closet.py
Everything that reasons over the whole wardrobe at once.

The graph answers questions about one garment; this module answers questions
about the collection: what to wear for the weather, what is missing for it, what
the wardrobe is worth, and what it says about the person who owns it. It reads
the wardrobe through graph.wardrobe() and computes in Python, because these are
aggregations and rankings rather than traversals, and writing them as Cypher
would hide the logic that is the interesting part.

Every recommendation here is a heuristic and is described as one. The system
knows what each garment is and how warm it is; turning that into "wear this
today" is a rule of thumb, not a measured result, and the thesis should not
present it as if a model had learned it.
"""

from config import (
    CATEGORY_WARMTH,
    DEFAULT_WASH,
    SEASON_ESSENTIALS,
    SEASONS,
    WASH_CARE,
)

_SEASON = {s["name"]: s for s in SEASONS}
_ORDER = [s["name"] for s in SEASONS]


# ---------------------------------------------------------------------------
# Care
# ---------------------------------------------------------------------------
def wash_for(item: dict) -> dict:
    """
    How to wash one garment: the owner's own setting if they gave one, otherwise
    the conservative default for its fibre.

    Returns temp_c, cycle, note and a source that says where the answer came
    from, so the interface can show "you set this" differently from "derived
    from wool".
    """
    if item.get("wash_temp") is not None or item.get("wash_cycle"):
        base = WASH_CARE.get(item.get("material") or "", DEFAULT_WASH)
        return {
            "temp_c": item.get("wash_temp", base["temp_c"]),
            "cycle": item.get("wash_cycle") or base["cycle"],
            "note": item.get("wash_note") or base["note"],
            "source": "you",
        }
    material = item.get("material")
    care = WASH_CARE.get(material)
    if care:
        return {**care, "source": f"typical for {material}"}
    return {**DEFAULT_WASH, "source": "default"}


# ---------------------------------------------------------------------------
# Value
# ---------------------------------------------------------------------------
def _priced(items: list[dict]) -> list[dict]:
    return [i for i in items if isinstance(i.get("price"), (int, float))]


def _slot(item: dict) -> str:
    """Which place in an outfit a garment fills, from its layer."""
    layer = item.get("layer")
    if layer == "full":
        return "full"
    if layer == "outer":
        return "outer"
    if layer == "bottom":
        return "bottom"
    return "top"  # base, mid, or unknown: something worn on the upper body


def _outfit(items: list[dict], pick):
    """
    Build one outfit by choosing garments with `pick` (max or min by price).

    An outfit is either a full-body piece or a top and a bottom, plus an
    optional outer layer. Only priced garments are considered, because an
    outfit's value is undefined the moment one of its pieces has no price.
    """
    by_slot: dict[str, list[dict]] = {"full": [], "top": [], "bottom": [], "outer": []}
    for i in _priced(items):
        by_slot[_slot(i)].append(i)

    def best(slot):
        return pick(by_slot[slot], key=lambda i: i["price"]) if by_slot[slot] else None

    top, bottom, full, outer = best("top"), best("bottom"), best("full"), best("outer")

    # a top-and-bottom outfit, or a one-piece, whichever is possible; when both
    # are, keep the one whose base value is more extreme in the chosen direction
    two_piece = [x for x in (top, bottom) if x] if (top and bottom) else []
    chosen = []
    if two_piece and full:
        two_total = sum(x["price"] for x in two_piece)
        chosen = two_piece if pick([two_total, full["price"]]) == two_total else [full]
    elif two_piece:
        chosen = two_piece
    elif full:
        chosen = [full]

    if outer and chosen:
        chosen = chosen + [outer]

    return chosen


def outfit_value(items: list[dict]) -> dict:
    """
    The most and least valuable outfit that can be assembled from priced
    garments, and the wardrobe's total worth.

    "Outfit" is a composed thing, not a stored one: the priciest top with the
    priciest bottom and the priciest coat is the most valuable outfit even if
    they were never worn together. That is a fair reading of the question and an
    honest one, as long as it is not dressed up as a real outfit the person owns.
    """
    priced = _priced(items)
    total = round(sum(i["price"] for i in priced), 2)

    most = _outfit(items, max)
    least = _outfit(items, min)

    def summarise(outfit):
        if not outfit:
            return None
        return {
            "total": round(sum(i["price"] for i in outfit), 2),
            "pieces": [{"id": i["id"], "category": i.get("category"),
                        "color": i.get("color"), "price": i["price"],
                        "photo_url": i.get("photo_url")} for i in outfit],
        }

    dearest = max(priced, key=lambda i: i["price"]) if priced else None
    return {
        "total_value": total,
        "priced": len(priced),
        "unpriced": len(items) - len(priced),
        "most_valuable_outfit": summarise(most),
        "least_valuable_outfit": summarise(least),
        "most_valuable_item": (
            {"id": dearest["id"], "category": dearest.get("category"),
             "price": dearest["price"], "photo_url": dearest.get("photo_url")}
            if dearest else None
        ),
    }


# ---------------------------------------------------------------------------
# Profile: what the wardrobe says about its owner
# ---------------------------------------------------------------------------
def _tally(items, key):
    counts: dict[str, int] = {}
    for i in items:
        v = i.get(key)
        if v:
            counts[v] = counts.get(v, 0) + 1
    return sorted(({"name": k, "n": n} for k, n in counts.items()),
                  key=lambda r: (-r["n"], r["name"]))


def profile(items: list[dict]) -> dict:
    """
    A person-facing read of their own wardrobe: what they mostly wear, the
    palette they buy in, how the collection splits across the body, and what it
    is worth. Counts, not judgements; the wardrobe describes itself.
    """
    styles = _tally(items, "style")
    colors = _tally(items, "color")
    materials = _tally(items, "material")
    regions = _tally(items, "region")

    return {
        "count": len(items),
        "dominant_style": styles[0]["name"] if styles else None,
        "dominant_color": colors[0]["name"] if colors else None,
        "styles": styles,
        "colors": colors,
        "materials": materials,
        "regions": regions,
        "value": outfit_value(items),
        "coverage": season_coverage(items),
        "gaps": gaps(items),
    }


# ---------------------------------------------------------------------------
# Weather coverage and the gaps in it
# ---------------------------------------------------------------------------
def _fits(item: dict, season: dict) -> bool:
    w = item.get("warmth")
    return w is not None and season["warmth_min"] <= w <= season["warmth_max"]


def season_coverage(items: list[dict]) -> list[dict]:
    """How many garments are wearable in each season's temperature window."""
    out = []
    for s in SEASONS:
        fitting = [i for i in items if _fits(i, s)]
        out.append({"name": s["name"], "temp_range": s["temp_range"],
                    "n": len(fitting)})
    return out


def gaps(items: list[dict]) -> list[dict]:
    """
    What the wardrobe cannot dress for.

    For each season, take the garments warm enough for it and ask whether they
    cover the body: something for the upper half, something for the lower half,
    and for the cold seasons an actual outer layer. A one-piece (a dress) covers
    both halves at once. Whatever is missing is reported as a concrete thing to
    acquire, which is the useful form of the answer, more than a coverage
    percentage would be.
    """
    out = []
    for s in SEASONS:
        need = SEASON_ESSENTIALS[s["name"]]
        fitting = [i for i in items if _fits(i, s)]

        covered = set()
        has_outer = False
        for i in fitting:
            region = i.get("region")
            if region == "full":
                covered.update(("upper", "lower"))
            elif region in ("upper", "lower"):
                covered.add(region)
            if i.get("layer") == "outer":
                has_outer = True

        missing = []
        for region in need["regions"]:
            if region not in covered:
                where = "upper body" if region == "upper" else "lower body"
                missing.append(f"nothing for the {where}")
        if need["outer"] and not has_outer:
            missing.append("no insulating outer layer (a coat or heavy jacket)")

        out.append({
            "season": s["name"],
            "temp_range": s["temp_range"],
            "fitting": len(fitting),
            "ready": not missing,
            "missing": missing,
        })
    return out


# ---------------------------------------------------------------------------
# The fit recommender
# ---------------------------------------------------------------------------
def _cat_warmth(item: dict) -> int:
    return CATEGORY_WARMTH.get(item.get("category") or "", (2, "base"))[0]


def _score(item: dict, prefs: dict) -> float:
    """
    How well one garment suits this person, before weather is considered.

    Preferences are hints and are weighted as such: a liked style or colour
    nudges a garment up, a disliked colour nudges it down, and the model's own
    confidence in what the garment is breaks remaining ties. Nothing here can
    exclude a garment outright, because it is the person's own wardrobe and they
    are allowed to wear the thing they said they dislike.
    """
    score = 0.0
    if item.get("style") in prefs.get("preferred_styles", []):
        score += 2.0
    if item.get("color") in prefs.get("preferred_colors", []):
        score += 1.5
    if item.get("color") in prefs.get("disliked_colors", []):
        score -= 2.0
    score += (item.get("category_confidence") or 0) * 0.5
    if item.get("corrected"):
        score += 0.5  # a human-confirmed label is worth trusting a little more
    return score


def recommend(items: list[dict], prefs: dict, season: str | None = None) -> dict:
    """
    Assemble one outfit for the weather from what the person actually owns.

    The target is a season's warmth window, shifted a point warmer or cooler if
    they said they run cold or warm. The recommender fills the outfit slot by
    slot, choosing within each the garment that fits the target warmth and best
    matches their taste. It is greedy and per-slot, not a search over whole
    outfits: good enough to be useful, simple enough to explain on a slide.

    Returns the chosen garments, the reasoning, and an honest note when the
    wardrobe cannot cover the weather rather than a padded-out fake outfit.
    """
    season = season or prefs.get("home_season") or "mild"
    if season not in _SEASON:
        season = "mild"
    window = _SEASON[season]

    shift = 0
    if prefs.get("runs_cold"):
        shift += 1     # feels the cold: aim one notch warmer
    if prefs.get("runs_warm"):
        shift -= 1
    target = (window["warmth_min"] + window["warmth_max"]) / 2 + shift

    def suitable(pool):
        # within the season window, best taste-match first, then closest to the
        # target warmth
        pool = [i for i in pool if _fits(i, window)]
        pool.sort(key=lambda i: (-_score(i, prefs), abs((i.get("warmth") or 0) - target)))
        return pool

    tops = suitable([i for i in items if _slot(i) == "top"])
    bottoms = suitable([i for i in items if _slot(i) == "bottom"])
    fulls = suitable([i for i in items if _slot(i) == "full"])
    outers = suitable([i for i in items if _slot(i) == "outer"])

    chosen, reasons = [], []
    need_outer = SEASON_ESSENTIALS[season]["outer"]

    # a one-piece is only proposed when it beats the best top on taste, so a
    # loved dress wins but a lone dress does not crowd out a real outfit
    if fulls and (not tops or _score(fulls[0], prefs) >= _score(tops[0], prefs)):
        chosen.append(fulls[0])
        reasons.append(f"{_describe(fulls[0])} as a one-piece")
    else:
        if tops:
            chosen.append(tops[0])
            reasons.append(f"{_describe(tops[0])} on top")
        if bottoms:
            chosen.append(bottoms[0])
            reasons.append(f"{_describe(bottoms[0])} below")

    if need_outer and outers:
        chosen.append(outers[0])
        reasons.append(f"{_describe(outers[0])} over it for the cold")

    missing = []
    covered = {_slot(i) for i in chosen}
    if "full" not in covered:
        if "top" not in covered:
            missing.append("a top warm enough for this weather")
        if "bottom" not in covered:
            missing.append("something for the lower body")
    if need_outer and not any(_slot(i) == "outer" for i in chosen):
        missing.append("an outer layer this warm")

    total_warmth = None
    if chosen:
        # a rough outfit warmth: the warmest piece carries it, the rest add a
        # little. This is a display number, not the per-garment score.
        warmths = sorted((i.get("warmth") or 0 for i in chosen), reverse=True)
        total_warmth = warmths[0] + sum(w * 0.3 for w in warmths[1:])
        total_warmth = round(min(11, total_warmth), 1)

    return {
        "season": season,
        "temp_range": window["temp_range"],
        "target_warmth": round(target, 1),
        "outfit": [_piece(i) for i in chosen],
        "reasons": reasons,
        "outfit_warmth": total_warmth,
        "missing": missing,
        "complete": not missing,
    }


def _describe(item: dict) -> str:
    parts = [item.get("color"), item.get("material"), item.get("category")]
    return " ".join(p for p in parts if p) or "an item"


def _piece(item: dict) -> dict:
    return {
        "id": item["id"],
        "category": item.get("category"),
        "color": item.get("color"),
        "material": item.get("material"),
        "layer": item.get("layer"),
        "warmth": item.get("warmth"),
        "price": item.get("price"),
        "photo_url": item.get("photo_url"),
    }
