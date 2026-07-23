"""
graph.py
Write garment tags into Neo4j as a knowledge graph and query them back.

Graph shape:
  (Garment {id, image_path, warmth, layer})
      -[:HAS_CATEGORY]-> (Category {name, warmth, layer})
      -[:MADE_OF]------> (Material {name, warmth})
      -[:HAS_STYLE]----> (Style {name})
      -[:HAS_COLOR]----> (Color {name})
      -[:HAS_SLEEVE]---> (Sleeve {name})

Plus a seeded ontology that no image touches:
  (Season {name, temp_range, warmth_min, warmth_max}) -[:COLDER_THAN]-> (Season)

The Season nodes are what makes this a knowledge graph and not a table of tags:
weather is never predicted by the model, it is derived by traversing from the
garment through its material and category into the season windows.

Neo4j Community is GPLv3. Fine for the thesis / internal use; for a commercial
SaaS look at the Neo4j Startup Program or a commercial license.
"""

from contextlib import contextmanager

from neo4j import GraphDatabase

from config import (
    CATEGORY_WARMTH,
    MATERIAL_WARMTH,
    NEO4J_PASSWORD,
    NEO4J_URI,
    NEO4J_USER,
    SEASONS,
)

# attribute group -> (relationship type, node label)
_REL = {
    "category": ("HAS_CATEGORY", "Category"),
    "material": ("MADE_OF", "Material"),
    "style": ("HAS_STYLE", "Style"),
    "color": ("HAS_COLOR", "Color"),
    "sleeve": ("HAS_SLEEVE", "Sleeve"),
}

_NODE_LABELS = ["Garment", "Category", "Material", "Style", "Color", "Sleeve", "Season"]


@contextmanager
def driver():
    d = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        yield d
    finally:
        d.close()


def ping() -> bool:
    """Return True if Neo4j is reachable."""
    try:
        with driver() as d:
            d.verify_connectivity()
        return True
    except Exception as e:
        print(f"Neo4j not reachable: {e}")
        return False


# ----------------------------------------------------------------------------
# Ontology (run once, or after editing the tables in config.py)
# ----------------------------------------------------------------------------
def seed_ontology() -> None:
    """
    Push the warmth tables and the season windows from config.py into Neo4j.
    Idempotent: MERGE + SET, so re-running after editing config just updates
    the numbers and leaves the stored garments alone.
    """
    with driver() as d, d.session() as s:
        for label in _NODE_LABELS:
            # id for Garment, name for everything else
            key = "id" if label == "Garment" else "name"
            s.run(
                f"CREATE CONSTRAINT {label.lower()}_{key} IF NOT EXISTS "
                f"FOR (n:{label}) REQUIRE n.{key} IS UNIQUE"
            )

        s.run(
            """
            UNWIND $rows AS row
            MERGE (m:Material {name: row.name})
            SET m.warmth = row.warmth
            """,
            rows=[{"name": k, "warmth": v} for k, v in MATERIAL_WARMTH.items()],
        )

        s.run(
            """
            UNWIND $rows AS row
            MERGE (c:Category {name: row.name})
            SET c.warmth = row.warmth, c.layer = row.layer
            """,
            rows=[
                {"name": k, "warmth": w, "layer": layer}
                for k, (w, layer) in CATEGORY_WARMTH.items()
            ],
        )

        s.run(
            """
            UNWIND $rows AS row
            MERGE (s:Season {name: row.name})
            SET s.temp_range = row.temp_range,
                s.warmth_min = row.warmth_min,
                s.warmth_max = row.warmth_max
            """,
            rows=SEASONS,
        )

        # chain the seasons so the graph reads as an ordered scale in the browser
        pairs = [
            {"warmer": a["name"], "colder": b["name"]}
            for a, b in zip(SEASONS, SEASONS[1:])
        ]
        s.run(
            """
            UNWIND $pairs AS p
            MATCH (w:Season {name: p.warmer}), (c:Season {name: p.colder})
            MERGE (c)-[:COLDER_THAN]->(w)
            """,
            pairs=pairs,
        )


# ----------------------------------------------------------------------------
# Garments
# ----------------------------------------------------------------------------
def save_garment(garment_id: str, image_path: str, tags: dict,
                 warmth: int | None = None, layer: str | None = None) -> None:
    """
    tags is the dict returned by classify(), e.g.
      {"category": {"label": "jeans", "confidence": 0.83}, ...}
    warmth/layer come from pipeline.weather and drive the season lookup.
    """
    with driver() as d, d.session() as s:
        s.run(
            """
            MERGE (g:Garment {id: $id})
            SET g.image_path = $path, g.warmth = $warmth, g.layer = $layer
            """,
            id=garment_id, path=image_path, warmth=warmth, layer=layer,
        )
        for group, (rel, node_label) in _REL.items():
            if group not in tags:
                continue
            value = tags[group]["label"]
            conf = tags[group]["confidence"]
            # node_label / rel are trusted (from _REL, not user input)
            s.run(
                f"""
                MATCH (g:Garment {{id: $id}})
                MERGE (n:{node_label} {{name: $value}})
                MERGE (g)-[r:{rel}]->(n)
                SET r.confidence = $conf
                """,
                id=garment_id, value=value, conf=conf,
            )


def infer_weather(garment_id: str) -> list[dict]:
    """
    Derive the weather a stored garment suits, by traversing the graph.

    Nothing here asks the model anything: it re-computes the warmth from the
    material and category nodes it is linked to, then matches the Season
    windows. Edit config.py + re-seed and every garment re-answers.
    """
    with driver() as d, d.session() as s:
        rows = s.run(
            """
            MATCH (g:Garment {id: $id})
            OPTIONAL MATCH (g)-[:MADE_OF]->(m:Material)
            OPTIONAL MATCH (g)-[:HAS_CATEGORY]->(c:Category)
            WITH g,
                 coalesce(g.warmth,
                          coalesce(m.warmth, 2) + coalesce(c.warmth, 2)) AS score
            MATCH (s:Season)
            WHERE score >= s.warmth_min AND score <= s.warmth_max
            RETURN s.name AS name, s.temp_range AS temp_range, score AS score
            ORDER BY s.warmth_min
            """,
            id=garment_id,
        )
        return [dict(row) for row in rows]


def find_by_attribute(group: str, value: str) -> list[str]:
    """Return garment ids that have the given attribute value."""
    if group not in _REL:
        raise ValueError(f"unknown group '{group}', pick from {list(_REL)}")
    rel, node_label = _REL[group]
    with driver() as d, d.session() as s:
        rows = s.run(
            f"""
            MATCH (g:Garment)-[:{rel}]->(n:{node_label} {{name: $value}})
            RETURN g.id AS id
            """,
            value=value,
        )
        return [row["id"] for row in rows]


def find_by_season(season: str) -> list[dict]:
    """Return garments whose warmth falls inside the given season's window."""
    with driver() as d, d.session() as s:
        rows = s.run(
            """
            MATCH (se:Season {name: $season})
            MATCH (g:Garment)-[:HAS_CATEGORY]->(c:Category)
            WHERE g.warmth >= se.warmth_min AND g.warmth <= se.warmth_max
            RETURN g.id AS id, c.name AS category, g.warmth AS warmth
            ORDER BY g.warmth
            """,
            season=season,
        )
        return [dict(row) for row in rows]
