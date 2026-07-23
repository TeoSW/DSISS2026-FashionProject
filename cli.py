"""
cli.py
Command-line entry point that ties the pipeline together.

  python cli.py test-db                       check Neo4j connection
  python cli.py seed                          load the warmth/season ontology
  python cli.py analyze photo.jpg             remove bg + CLIP tags + weather
  python cli.py analyze photo.jpg --save      also store the result in Neo4j
  python cli.py analyze photo.jpg --json      raw JSON instead of the summary
  python cli.py query --material cotton       list stored garments by attribute
  python cli.py query --season cold           list stored garments by weather

Run the database first:  docker compose up -d  &&  python cli.py seed
"""

import argparse
import json
import sys
import uuid

from config import SEASONS
from pipeline import classify, graph, remove_bg, weather

_GROUPS = ("category", "material", "style", "color", "sleeve")


def _summary(tags: dict, score: int, seasons: list[dict]) -> str:
    """One human-readable paragraph instead of a wall of JSON."""
    def lbl(group):
        return tags.get(group, {}).get("label", "?")

    def pct(group):
        return f"{tags.get(group, {}).get('confidence', 0) * 100:.0f}%"

    lines = [
        f"  item      {lbl('color')} {lbl('material')} {lbl('category')}, {lbl('sleeve')}",
        f"  style     {lbl('style')}",
        f"  warmth    {score}/11  (layer: {weather.layer_of(tags)})",
    ]
    if seasons:
        pretty = ", ".join(f"{s['name']} ({s['temp_range']})" for s in seasons)
        lines.append(f"  weather   {pretty}")
    else:
        lines.append("  weather   no season window matched")
    lines.append(
        "  confidence  "
        + "  ".join(f"{g}={pct(g)}" for g in _GROUPS if g in tags)
    )
    return "\n".join(lines)


def cmd_test_db(_args):
    ok = graph.ping()
    print("Neo4j OK" if ok else "Neo4j NOT reachable (is `docker compose up -d` running?)")
    sys.exit(0 if ok else 1)


def cmd_seed(_args):
    if not graph.ping():
        sys.exit(1)
    graph.seed_ontology()
    print(
        f"ontology loaded: {len(SEASONS)} seasons + material/category warmth tables"
    )


def cmd_analyze(args):
    print(f"removing background: {args.image}")
    cutout = remove_bg.remove_background(args.image)
    rgb = remove_bg.on_white(cutout)

    print("classifying (first run downloads the CLIP model, ~600MB)...")
    tags = classify.classify(rgb)
    score = weather.warmth_score(tags)

    garment_id = None
    if args.save:
        garment_id = uuid.uuid4().hex[:12]
        graph.save_garment(
            garment_id, args.image, tags,
            warmth=score, layer=weather.layer_of(tags),
        )
        # asked of the graph, not of the model
        seasons = graph.infer_weather(garment_id)
        if not seasons:
            print("no Season nodes in the graph -- run `python cli.py seed` first")
            seasons = weather.seasons_for(score)
    else:
        seasons = weather.seasons_for(score)

    if args.json:
        print(json.dumps(
            {"id": garment_id, "tags": tags, "warmth": score, "seasons": seasons},
            indent=2,
        ))
    else:
        print()
        print(_summary(tags, score, seasons))

    if garment_id:
        print(f"\nsaved to Neo4j as Garment id={garment_id}")


def cmd_query(args):
    if args.season:
        rows = graph.find_by_season(args.season)
        if not rows:
            print(f"no garments for season={args.season}")
            return
        print(f"{len(rows)} garment(s) for {args.season} weather:")
        for r in rows:
            print(f"  {r['id']}  {r['category']}  (warmth {r['warmth']})")
        return

    group, value = None, None
    for g in _GROUPS:
        v = getattr(args, g.replace("-", "_"))
        if v:
            group, value = g, v
            break
    if group is None:
        print("pick one filter, e.g. --material cotton or --season cold")
        sys.exit(1)

    ids = graph.find_by_attribute(group, value)
    if ids:
        print(f"{len(ids)} garment(s) with {group}={value}:")
        for gid in ids:
            print(f"  {gid}")
    else:
        print(f"no garments with {group}={value}")


def main():
    parser = argparse.ArgumentParser(description="Fashion recognition CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("test-db", help="check Neo4j connection").set_defaults(func=cmd_test_db)

    sub.add_parser(
        "seed", help="load the warmth/season ontology into Neo4j"
    ).set_defaults(func=cmd_seed)

    a = sub.add_parser("analyze", help="tag one image")
    a.add_argument("image")
    a.add_argument("--save", action="store_true", help="store result in Neo4j")
    a.add_argument("--json", action="store_true", help="print raw JSON")
    a.set_defaults(func=cmd_analyze)

    q = sub.add_parser("query", help="query stored garments")
    q.add_argument("--category")
    q.add_argument("--material")
    q.add_argument("--style")
    q.add_argument("--color")
    q.add_argument("--sleeve")
    q.add_argument("--season", choices=[s["name"] for s in SEASONS])
    q.set_defaults(func=cmd_query)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
