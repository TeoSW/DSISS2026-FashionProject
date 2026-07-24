"""
photos.py
The picture that belongs to a stored garment.

Neo4j holds facts about a garment, not megabytes of pixels: the graph stores a
path and the file lives next to it on disk. That keeps the database small enough
to dump and inspect, and it means deleting a garment is two operations that can
both fail, which is why delete() never raises.

What is kept is the cutout, not the original photograph. It is what the model
actually looked at, it has no background to distract from the garment, and a
wardrobe full of transparent cutouts reads as a wardrobe rather than as a
folder of holiday snaps.

data/ is gitignored, so nothing here is ever committed or redistributed.
"""

from pathlib import Path

from PIL import Image

WARDROBE = Path("data/wardrobe")

# Long enough to look sharp on a retina screen at card size, small enough that a
# hundred garments is a few megabytes rather than a few hundred.
MAX_SIDE = 640


def save(garment_id: str, image: Image.Image) -> str:
    """Write the garment's picture and return the path stored on the node."""
    WARDROBE.mkdir(parents=True, exist_ok=True)
    out = WARDROBE / f"{garment_id}.png"

    copy = image.copy()
    copy.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
    if copy.mode not in ("RGBA", "RGB"):
        copy = copy.convert("RGBA")
    copy.save(out, "PNG", optimize=True)
    return str(out).replace("\\", "/")


def path(garment_id: str) -> Path | None:
    """Where a garment's picture is, or None if it was never stored."""
    p = WARDROBE / f"{garment_id}.png"
    return p if p.exists() else None


def delete(garment_id: str) -> bool:
    """Remove the picture. Missing is success: the caller wanted it gone."""
    p = WARDROBE / f"{garment_id}.png"
    try:
        p.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def usage() -> dict:
    """How many pictures and how much disk, for the statistics panel."""
    if not WARDROBE.exists():
        return {"files": 0, "bytes": 0}
    files = list(WARDROBE.glob("*.png"))
    return {"files": len(files), "bytes": sum(f.stat().st_size for f in files)}
