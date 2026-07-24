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
  (Category) -[:WORN_ON]-> (Region {name})        upper / lower / full
  (Season {name, temp_range, warmth_min, warmth_max}) -[:COLDER_THAN]-> (Season)
  (Dataset {name, license, usage}) -[:HAS_CLASS]-> (DatasetClass) -[:MAPS_TO]-> (Category)
  (Garment) -[:FROM_DATASET]-> (Dataset)

And what people say back (see pipeline/feedback.py):
  (Correction {id, verdict, note, created_at}) -[:ABOUT]-> (Garment)
  (Correction) -[:PREDICTED {group, confidence}]-> (Category|Material|...)
  (Correction) -[:SHOULD_BE {group}]-> (Category|Material|...)

Every attribute edge carries source: 'model' or 'human'. That one property is
what lets the graph hold a corrected fact and a predicted one side by side and
still know which is which.

The Season nodes are what makes this a knowledge graph and not a table of tags:
weather is never predicted by the model, it is derived by traversing from the
garment through its material and category into the season windows.

Neo4j Community is GPLv3. Fine for the thesis / internal use; for a commercial
SaaS look at the Neo4j Startup Program or a commercial license.
"""

from contextlib import contextmanager

from neo4j import GraphDatabase

from config import (
    ATTRIBUTES,
    CATEGORY_REGION,
    CATEGORY_WARMTH,
    DATASETS,
    FASHION_MNIST_MAP,
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

_NODE_LABELS = [
    "Garment", "Category", "Material", "Style", "Color", "Sleeve", "Season",
    "Dataset", "DatasetClass", "Correction", "Region",
]

# these are keyed by id, everything else by name
_ID_KEYED = {"Garment", "Correction"}


@contextmanager
def driver():
    # notifications off: on an empty graph the server warns that HAS_CATEGORY
    # and friends "do not exist" for every query, which is true and useless.
    d = GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USER, NEO4J_PASSWORD),
        notifications_min_severity="OFF",
    )
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
            key = "id" if label in _ID_KEYED else "name"
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

        # Which part of the body each category is worn on. The two-stage
        # experiment used this table as a prompt trick and it did not pay off;
        # here it earns its keep as structure, because it is what the wardrobe
        # is organised by. Clicking the mannequin runs this traversal.
        s.run(
            """
            UNWIND $rows AS row
            MERGE (r:Region {name: row.region})
            WITH r, row
            MATCH (c:Category {name: row.category})
            MERGE (c)-[:WORN_ON]->(r)
            """,
            rows=[{"category": c, "region": r} for c, r in CATEGORY_REGION.items()],
        )

        # the label vocabulary CLIP chooses from, so the graph shows every
        # possible answer and not only the ones some photo happened to hit
        for group, node_label in (
            ("style", "Style"), ("color", "Color"), ("sleeve", "Sleeve")
        ):
            s.run(
                f"UNWIND $names AS n MERGE (x:{node_label} {{name: n}})",
                names=ATTRIBUTES[group],
            )

        _seed_datasets(s)


def _seed_datasets(s) -> None:
    """
    Where images may come from and what may be done with them (see scraper.py).

    Each Fashion-MNIST class becomes a node linked to the Category it
    corresponds to; the four classes with no counterpart (bags, three kinds of
    footwear) stay unlinked on purpose -- that dangling edge is the honest
    picture of how far the baseline dataset covers this ontology.
    """
    s.run(
        """
        UNWIND $rows AS row
        MERGE (d:Dataset {name: row.name})
        SET d.title = row.title, d.license = row.license, d.usage = row.usage,
            d.source = row.source, d.images = row.images, d.note = row.note
        """,
        rows=DATASETS,
    )

    rows = [
        {"key": f"fashion_mnist/{cls}", "cls": cls, "idx": i, "category": cat}
        for i, (cls, cat) in enumerate(FASHION_MNIST_MAP.items())
    ]
    s.run(
        """
        MATCH (d:Dataset {name: 'fashion_mnist'})
        UNWIND $rows AS row
        MERGE (k:DatasetClass {name: row.key})
        SET k.class_name = row.cls, k.label_id = row.idx, k.dataset = 'fashion_mnist'
        MERGE (d)-[:HAS_CLASS]->(k)
        """,
        rows=rows,
    )
    s.run(
        """
        UNWIND [r IN $rows WHERE r.category IS NOT NULL] AS row
        MATCH (k:DatasetClass {name: row.key})
        MATCH (c:Category {name: row.category})
        MERGE (k)-[:MAPS_TO]->(c)
        """,
        rows=rows,
    )


# ----------------------------------------------------------------------------
# Garments
# ----------------------------------------------------------------------------
def save_garment(garment_id: str, image_path: str, tags: dict,
                 warmth: int | None = None, layer: str | None = None,
                 dataset: str | None = None, photo: str | None = None,
                 source: str = "model") -> None:
    """
    tags is the dict returned by classify(), e.g.
      {"category": {"label": "jeans", "confidence": 0.83}, ...}
    warmth/layer come from pipeline.weather and drive the season lookup.
    dataset, when given, links the garment to its Dataset node so its licence
    travels with it. photo is where pipeline.photos wrote the cutout.

    created_at is set ON CREATE only: re-saving a garment must not make it look
    newly added, or the wardrobe reorders itself for no reason.
    """
    with driver() as d, d.session() as s:
        s.run(
            """
            MERGE (g:Garment {id: $id})
            ON CREATE SET g.created_at = datetime()
            SET g.image_path = $path, g.warmth = $warmth, g.layer = $layer,
                g.photo = $photo, g.source = $source
            """,
            id=garment_id, path=image_path, warmth=warmth, layer=layer,
            photo=photo, source=source,
        )
        if dataset:
            s.run(
                """
                MATCH (g:Garment {id: $id})
                MERGE (d:Dataset {name: $dataset})
                MERGE (g)-[:FROM_DATASET]->(d)
                """,
                id=garment_id, dataset=dataset,
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
                SET r.confidence = $conf, r.source = 'model'
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


def stats() -> dict:
    """Node counts per label and relationship counts per type, for `cli.py stats`."""
    with driver() as d, d.session() as s:
        nodes = s.run(
            "MATCH (n) UNWIND labels(n) AS l "
            "RETURN l AS label, count(*) AS n ORDER BY label"
        )
        nodes = {r["label"]: r["n"] for r in nodes}
        rels = s.run(
            "MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS n ORDER BY type"
        )
        rels = {r["type"]: r["n"] for r in rels}
    return {"nodes": nodes, "relationships": rels}


# ----------------------------------------------------------------------------
# The wardrobe
# ----------------------------------------------------------------------------
def wardrobe(region: str | None = None) -> list[dict]:
    """
    Everything stored, with the attributes needed to draw it on a shelf.

    One query rather than one per garment, and every attribute is an OPTIONAL
    MATCH: a garment with a missing edge is a garment with a gap on its card,
    not a garment that vanishes from the wardrobe.

    `corrected` is true when any of its edges was written by a person. The
    wardrobe marks those, because a shelf where the human answer and the model
    answer look identical hides the only interesting thing about it.
    """
    with driver() as d, d.session() as s:
        rows = s.run(
            """
            MATCH (g:Garment)
            OPTIONAL MATCH (g)-[rc:HAS_CATEGORY]->(c:Category)
            OPTIONAL MATCH (c)-[:WORN_ON]->(r:Region)
            OPTIONAL MATCH (g)-[rm:MADE_OF]->(m:Material)
            OPTIONAL MATCH (g)-[rs:HAS_STYLE]->(st:Style)
            OPTIONAL MATCH (g)-[rk:HAS_COLOR]->(col:Color)
            OPTIONAL MATCH (g)-[rl:HAS_SLEEVE]->(sl:Sleeve)
            WITH g, c, r, m, st, col, sl, rc, rm, rs, rk, rl,
                 [x IN [rc, rm, rs, rk, rl] WHERE x.source = 'human'] AS human
            WHERE $region IS NULL OR r.name = $region
            OPTIONAL MATCH (se:Season)
              WHERE g.warmth >= se.warmth_min AND g.warmth <= se.warmth_max
            WITH g, c, r, m, st, col, sl, rc, rm, rk, human,
                 collect(DISTINCT {name: se.name, temp_range: se.temp_range}) AS seasons
            RETURN g.id AS id,
                   g.warmth AS warmth,
                   g.layer AS layer,
                   g.photo AS photo,
                   g.image_path AS image_path,
                   toString(g.created_at) AS created_at,
                   c.name AS category,
                   coalesce(r.name, 'unplaced') AS region,
                   m.name AS material,
                   st.name AS style,
                   col.name AS color,
                   sl.name AS sleeve,
                   rc.confidence AS category_confidence,
                   rm.confidence AS material_confidence,
                   rk.confidence AS color_confidence,
                   size(human) > 0 AS corrected,
                   seasons AS seasons
            ORDER BY g.created_at DESC
            """,
            region=region,
        )
        out = []
        for row in rows:
            item = dict(row)
            item["seasons"] = [s for s in item["seasons"] if s.get("name")]
            out.append(item)
        return out


def region_counts() -> dict:
    """How many garments hang on each part of the mannequin."""
    with driver() as d, d.session() as s:
        rows = s.run(
            """
            MATCH (g:Garment)-[:HAS_CATEGORY]->(:Category)-[:WORN_ON]->(r:Region)
            RETURN r.name AS region, count(*) AS n
            """
        )
        counts = {r["region"]: r["n"] for r in rows}
        loose = s.run(
            """
            MATCH (g:Garment)
            WHERE NOT (g)-[:HAS_CATEGORY]->(:Category)-[:WORN_ON]->(:Region)
            RETURN count(*) AS n
            """
        ).single()["n"]
    if loose:
        counts["unplaced"] = loose
    return counts


def delete_garment(garment_id: str) -> bool:
    """
    Remove one garment and every edge it owns. Returns False if it was not
    there, so the caller can answer 404 instead of pretending it deleted
    something. The Correction nodes about it survive on purpose: what the model
    got wrong is evidence, and deleting the garment does not unmake the mistake.
    """
    with driver() as d, d.session() as s:
        n = s.run(
            """
            MATCH (g:Garment {id: $id})
            OPTIONAL MATCH (g)-[r]-()
            DELETE r, g
            RETURN count(g) AS n
            """,
            id=garment_id,
        ).single()["n"]
    return n > 0


def insights() -> dict:
    """
    Aggregates for the statistics panel, counted by the database rather than
    by pulling every garment into Python and tallying it there.

    Every figure here describes what has been stored, not how good the model
    is. Accuracy lives in evaluate.py against labelled ground truth; a wardrobe
    can only ever tell you what it contains.
    """
    with driver() as d, d.session() as s:
        def tally(query, **params):
            return [dict(r) for r in s.run(query, **params)]

        by_category = tally(
            """
            MATCH (g:Garment)-[r:HAS_CATEGORY]->(c:Category)
            OPTIONAL MATCH (c)-[:WORN_ON]->(reg:Region)
            RETURN c.name AS name, count(*) AS n,
                   avg(r.confidence) AS confidence,
                   coalesce(reg.name, 'unplaced') AS region
            ORDER BY n DESC, name
            """
        )
        by_material = tally(
            """
            MATCH (g:Garment)-[r:MADE_OF]->(m:Material)
            RETURN m.name AS name, count(*) AS n, avg(r.confidence) AS confidence,
                   m.warmth AS warmth
            ORDER BY n DESC, name
            """
        )
        by_color = tally(
            """
            MATCH (g:Garment)-[:HAS_COLOR]->(c:Color)
            RETURN c.name AS name, count(*) AS n ORDER BY n DESC, name
            """
        )
        by_style = tally(
            """
            MATCH (g:Garment)-[:HAS_STYLE]->(x:Style)
            RETURN x.name AS name, count(*) AS n ORDER BY n DESC, name
            """
        )
        by_layer = tally(
            """
            MATCH (g:Garment) WHERE g.layer IS NOT NULL
            RETURN g.layer AS name, count(*) AS n ORDER BY n DESC, name
            """
        )
        warmth = tally(
            """
            MATCH (g:Garment) WHERE g.warmth IS NOT NULL
            RETURN g.warmth AS warmth, count(*) AS n ORDER BY warmth
            """
        )
        by_season = tally(
            """
            MATCH (se:Season)
            OPTIONAL MATCH (g:Garment)
              WHERE g.warmth >= se.warmth_min AND g.warmth <= se.warmth_max
            RETURN se.name AS name, se.temp_range AS temp_range,
                   count(g) AS n, se.warmth_min AS warmth_min,
                   se.warmth_max AS warmth_max
            ORDER BY se.warmth_min
            """
        )
        totals = s.run(
            """
            MATCH (g:Garment)
            WITH count(g) AS garments, avg(g.warmth) AS mean_warmth
            OPTIONAL MATCH (:Garment)-[r]->() WHERE r.source = 'human'
            RETURN garments, mean_warmth, count(r) AS human_edges
            """
        ).single()
        confidence = s.run(
            """
            MATCH (:Garment)-[r]->() WHERE r.confidence IS NOT NULL
            RETURN avg(r.confidence) AS mean, min(r.confidence) AS min,
                   count(r) AS edges
            """
        ).single()
        low = s.run(
            """
            MATCH (:Garment)-[r]->() WHERE r.confidence < 0.4
            RETURN count(r) AS n
            """
        ).single()["n"]

    return {
        "totals": {
            "garments": totals["garments"],
            "mean_warmth": round(totals["mean_warmth"], 2) if totals["mean_warmth"] else None,
            "human_edges": totals["human_edges"],
            "mean_confidence": round(confidence["mean"], 3) if confidence["mean"] else None,
            "attribute_edges": confidence["edges"],
            "low_confidence_edges": low,
        },
        "by_category": by_category,
        "by_material": by_material,
        "by_color": by_color,
        "by_style": by_style,
        "by_layer": by_layer,
        "by_season": by_season,
        "warmth": warmth,
        "regions": region_counts(),
    }


# ----------------------------------------------------------------------------
# Corrections
# ----------------------------------------------------------------------------
def save_correction(feedback_id: str, verdict: str, predicted: dict,
                    corrected: dict, note: str = "",
                    garment_id: str | None = None, model: str = "") -> None:
    """
    Record what a person said about one analysis.

    The Correction node points at both labels, the one the model chose and the
    one it should have chosen, so the mistake stays queryable as a pair. Ask the
    graph which confusion is most common and it answers in Cypher, without ever
    reading the JSONL corpus:

      MATCH (c:Correction)-[p:PREDICTED]->(a), (c)-[s:SHOULD_BE]->(b)
      WHERE p.group = 'category' AND s.group = 'category'
      RETURN a.name, b.name, count(*) AS n ORDER BY n DESC
    """
    with driver() as d, d.session() as s:
        s.run(
            """
            MERGE (c:Correction {id: $id})
            SET c.verdict = $verdict, c.note = $note, c.model = $model,
                c.created_at = datetime()
            """,
            id=feedback_id, verdict=verdict, note=note, model=model,
        )
        if garment_id:
            s.run(
                """
                MATCH (c:Correction {id: $id})
                MATCH (g:Garment {id: $garment})
                MERGE (c)-[:ABOUT]->(g)
                """,
                id=feedback_id, garment=garment_id,
            )

        for group, actual in corrected.items():
            if group not in _REL:
                continue
            _, node_label = _REL[group]
            was = predicted.get(group, {})
            s.run(
                f"""
                MATCH (c:Correction {{id: $id}})
                MERGE (b:{node_label} {{name: $actual}})
                MERGE (c)-[r:SHOULD_BE]->(b)
                SET r.group = $group
                """,
                id=feedback_id, actual=actual, group=group,
            )
            if was.get("label"):
                s.run(
                    f"""
                    MATCH (c:Correction {{id: $id}})
                    MERGE (a:{node_label} {{name: $was}})
                    MERGE (c)-[r:PREDICTED]->(a)
                    SET r.group = $group, r.confidence = $conf
                    """,
                    id=feedback_id, was=was["label"], group=group,
                    conf=was.get("confidence"),
                )


def apply_correction(garment_id: str, corrected: dict,
                     warmth: int | None = None, layer: str | None = None) -> None:
    """
    Re-point a stored garment's edges at the corrected labels.

    This is the half of the loop that pays off immediately. The old edge is
    deleted rather than kept alongside, because a garment has one category, and
    the new one is marked source='human' with confidence 1.0 so a later query
    can tell a person's answer from the model's. Since infer_weather() reads the
    graph and not the model, the seasons change the moment this runs.
    """
    with driver() as d, d.session() as s:
        for group, actual in corrected.items():
            if group not in _REL:
                continue
            rel, node_label = _REL[group]
            s.run(
                f"""
                MATCH (g:Garment {{id: $id}})-[r:{rel}]->()
                DELETE r
                """,
                id=garment_id,
            )
            s.run(
                f"""
                MATCH (g:Garment {{id: $id}})
                MERGE (n:{node_label} {{name: $actual}})
                MERGE (g)-[r:{rel}]->(n)
                SET r.confidence = 1.0, r.source = 'human'
                """,
                id=garment_id, actual=actual,
            )
        if warmth is not None:
            s.run(
                """
                MATCH (g:Garment {id: $id})
                SET g.warmth = $warmth, g.layer = $layer, g.corrected = true
                """,
                id=garment_id, warmth=warmth, layer=layer,
            )


def correction_stats() -> dict:
    """
    The confusion table as the graph sees it, per attribute group.

    Same question the JSONL corpus answers, asked of the knowledge graph
    instead, which is the point: once a correction is a node, counting mistakes
    is a query and not a script.
    """
    with driver() as d, d.session() as s:
        total = s.run(
            "MATCH (c:Correction) RETURN c.verdict AS verdict, count(*) AS n"
        )
        verdicts = {r["verdict"]: r["n"] for r in total}
        rows = s.run(
            """
            MATCH (c:Correction)-[p:PREDICTED]->(a)
            MATCH (c)-[q:SHOULD_BE]->(b)
            WHERE p.group = q.group
            RETURN p.group AS group, a.name AS predicted, b.name AS actual,
                   count(*) AS n
            ORDER BY n DESC, group
            """
        )
        confusions = [dict(r) for r in rows]
    confirmed = verdicts.get("correct", 0)
    wrong = verdicts.get("wrong", 0)
    return {
        "confirmed": confirmed,
        "wrong": wrong,
        "total": confirmed + wrong,
        "confusions": confusions,
    }


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
