"""
prefs.py
One person's taste, kept in a small JSON file.

There is no user system here, and the thesis does not need one: a single
wardrobe belongs to a single person, so their preferences are a single file
rather than a table keyed by an account that does not exist. The recommender
reads these to break ties between garments that are equally warm, and the gap
analysis reads the home temperature to know which season to plan for.

Kept deliberately small. Everything in it is a hint, never a hard filter: a
person who dislikes a colour should see fewer of it recommended, not have a
third of their own wardrobe hidden from them.
"""

import json
from pathlib import Path

STORE = Path("data/preferences.json")

DEFAULTS = {
    # styles pulled up in recommendations; empty means no preference
    "preferred_styles": [],
    # colours pulled up, and colours pushed down
    "preferred_colors": [],
    "disliked_colors": [],
    # the temperature this person actually keeps their home / commute at,
    # which is what "what should I wear today" is answered against when no
    # season is named
    "home_season": "mild",
    # how much they feel the cold: shifts the recommended warmth up or down a
    # point, because the same 10 C is a coat to one person and a shirt to another
    "runs_cold": False,
    "runs_warm": False,
}


def load() -> dict:
    """Current preferences, defaults filled in for anything missing or corrupt."""
    data = {}
    if STORE.exists():
        try:
            data = json.loads(STORE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    return {**DEFAULTS, **{k: data[k] for k in DEFAULTS if k in data}}


def save(update: dict) -> dict:
    """
    Merge a partial update over the stored preferences and write it back. Only
    known keys are kept, so a stray field from the browser cannot wander into
    the file, and the returned value is exactly what was stored.
    """
    current = load()
    for key in DEFAULTS:
        if key in update:
            current[key] = update[key]
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8")
    return current
