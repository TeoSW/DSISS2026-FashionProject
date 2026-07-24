"""
pricing.py
Turn a brand tag into a rough price, honestly.

The model reads what a garment is; the brand is the one thing the owner can add
that says roughly what it cost. This maps brand + category to a figure by
scaling a per-category base price by the brand's market tier. It is an estimate
and everything that shows it says so: a real price needs a live product feed,
and inventing a precise number would be worse than a labelled guess.

An unknown brand is not refused. It is treated as mid-range and the estimate
carries that caveat, because "about a mid-range price" is more useful than
nothing and the owner corrects it in one tap regardless.
"""

from config import (
    BRAND_TIERS,
    CATEGORY_BASE_PRICE,
    DEFAULT_BASE_PRICE,
    TIER_MULTIPLIER,
)


def normalise(brand: str | None) -> str:
    return (brand or "").strip().lower()


def tier_of(brand: str | None) -> str | None:
    """The market tier for a known brand, or None if it is not in the table."""
    return BRAND_TIERS.get(normalise(brand))


def estimate(brand: str | None, category: str | None) -> tuple[float | None, dict]:
    """
    A rough price for a brand + category, and the reasoning behind it.

    Returns (price, info). price is None only when there is no brand to go on,
    in which case nothing is guessed. info always explains the basis, so the UI
    can show "estimated: Zara is mid-tier" rather than a bare number that looks
    more certain than it is.
    """
    name = normalise(brand)
    if not name:
        return None, {"brand": None, "tier": None, "known": False,
                      "basis": "no brand given, so no estimate"}

    tier = BRAND_TIERS.get(name)
    known = tier is not None
    tier = tier or "mid"
    base = CATEGORY_BASE_PRICE.get(category or "", DEFAULT_BASE_PRICE)
    price = round(base * TIER_MULTIPLIER[tier], 2)

    if known:
        basis = f"{brand} is {tier}-tier; {category or 'garment'} base {base} {'€'}"
    else:
        basis = f"{brand} not in the table, assumed mid-range"
    return price, {"brand": brand, "tier": tier, "known": known, "basis": basis}
