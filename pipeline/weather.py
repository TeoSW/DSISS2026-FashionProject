"""
weather.py
Turn CLIP's visual tags into a single warmth score.

CLIP tells us *what* the garment is (wool, coat, long sleeves). It cannot tell
us what weather it is for, because that is knowledge, not pixels. Here we do the
one arithmetic step: material warmth + category warmth + sleeve adjustment.

The score is stored on the Garment node; matching it against seasons happens in
Cypher (see graph.infer_weather), so the rule that "7-9 means cold" lives in the
knowledge graph and can be changed without touching Python.

Two things the expanded ontology forced:

  * a sleeve length only means something for the layers worn on the torso. A
    pair of jeans, a boot and a wristwatch all get a sleeve label if you ask for
    one, and all three answers are noise.
  * some things are not weather at all. The arithmetic still runs on a
    wristwatch, because it is the same arithmetic, but the answer claims no
    season -- otherwise a wardrobe reports itself ready for winter on the
    strength of a bracelet.
"""

from config import (
    CATEGORY_WARMTH,
    MATERIAL_WARMTH,
    SEASONS,
    SLEEVE_MODIFIER,
    SLEEVED_LAYERS,
    is_seasonal,
)


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
    if layer in SLEEVED_LAYERS:
        score += SLEEVE_MODIFIER.get(sleeve, 0)
    return max(1, min(11, score))


def layer_of(tags: dict) -> str:
    """
    Where the item sits in an outfit: base / mid / outer / bottom / full, or one
    of the regions that are their own layer -- feet, head, neck, hands, waist,
    carried.
    """
    category = tags.get("category", {}).get("label", "")
    return CATEGORY_WARMTH.get(category, (2, "base"))[1]


def seasonal(tags: dict) -> bool:
    """Whether this item's warmth says anything about the weather at all."""
    return is_seasonal(tags.get("category", {}).get("label"))


def seasons_for(score: int, tags: dict | None = None) -> list[dict]:
    """
    Local fallback used when Neo4j is not running. Same windows the graph is
    seeded with, so `analyze` and `analyze --save` always agree.

    Pass the tags and a non-seasonal category claims no window: a ring is not
    freezing-weather equipment just because it is made of metal.
    """
    if tags is not None and not seasonal(tags):
        return []
    return [s for s in SEASONS if s["warmth_min"] <= score <= s["warmth_max"]]
