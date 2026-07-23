"""
weather.py
Turn CLIP's visual tags into a single warmth score.

CLIP tells us *what* the garment is (wool, coat, long sleeves). It cannot tell
us what weather it is for, because that is knowledge, not pixels. Here we do the
one arithmetic step: material warmth + category warmth + sleeve adjustment.

The score is stored on the Garment node; matching it against seasons happens in
Cypher (see graph.infer_weather), so the rule that "7-9 means cold" lives in the
knowledge graph and can be changed without touching Python.
"""

from config import CATEGORY_WARMTH, MATERIAL_WARMTH, SEASONS, SLEEVE_MODIFIER


def warmth_score(tags: dict) -> int:
    """
    tags is the dict returned by classify(). Unknown labels count as neutral (2),
    so a new label in config.ATTRIBUTES does not crash the pipeline.
    """
    material = tags.get("material", {}).get("label", "")
    category = tags.get("category", {}).get("label", "")
    sleeve = tags.get("sleeve", {}).get("label", "")

    cat_warmth, layer = CATEGORY_WARMTH.get(category, (2, "base"))
    score = MATERIAL_WARMTH.get(material, 2) + cat_warmth
    # trousers have no sleeves; whatever CLIP guessed there is noise
    if layer != "bottom":
        score += SLEEVE_MODIFIER.get(sleeve, 0)
    return max(1, min(11, score))


def layer_of(tags: dict) -> str:
    """base / mid / outer / bottom / full -- where the item sits in an outfit."""
    category = tags.get("category", {}).get("label", "")
    return CATEGORY_WARMTH.get(category, (2, "base"))[1]


def seasons_for(score: int) -> list[dict]:
    """
    Local fallback used when Neo4j is not running. Same windows the graph is
    seeded with, so `analyze` and `analyze --save` always agree.
    """
    return [s for s in SEASONS if s["warmth_min"] <= score <= s["warmth_max"]]
