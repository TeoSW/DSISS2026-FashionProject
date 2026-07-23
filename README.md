# DSISS-2026-Code

Clothing recognition pipeline: photo → background removal → CLIP tags → Neo4j knowledge graph.
CLI first, frontend later.

## Stack & licenses (commercial-clean path)

| Piece | Role | License |
|-------|------|---------|
| rembg + U2Net | background removal | MIT / Apache 2.0 |
| CLIP | zero-shot tagging | MIT |
| Neo4j Community | knowledge graph | GPLv3 (Startup Program for SaaS) |
| Fashionpedia | **eval / research only** | annotations CC-BY 4.0; images = 3rd-party |

The commercial product runs **zero-shot on the user's own images** — nothing is trained on
Fashionpedia images, so there is no image-licensing risk. Fashionpedia is used only to measure
accuracy in the thesis.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install -r requirements.txt
copy .env.example .env            # Windows (cp on Linux/Mac)
```

## Run the database

```bash
docker compose up -d
```

Neo4j browser: http://localhost:7474 (user `neo4j`, password `parola123`).

## Use the CLI

```bash
python cli.py test-db                     # check the DB connection
python cli.py seed                        # load the warmth/season ontology (once)
python cli.py analyze photo.jpg           # background removal + tags + weather
python cli.py analyze photo.jpg --save    # also store in Neo4j
python cli.py analyze photo.jpg --json    # raw JSON instead of the summary
python cli.py query --material cotton     # list stored garments by attribute
python cli.py query --season cold         # list stored garments by weather
```

First `analyze` downloads the CLIP model (~600MB), then it is cached.

```
  item      black wool coat, long sleeves
  style     casual
  warmth    11/11  (layer: outer)
  weather   freezing (below 0 C)
```

## Where the weather answer comes from

CLIP can only report what is visible: wool, coat, long sleeves. It has no idea
what temperature that is for. Weather is derived in the graph instead:

1. every `Material` and `Category` node carries a warmth weight (1–5), seeded
   from the tables in `config.py`;
2. a garment's warmth = material + category, adjusted for sleeves (skipped for
   trousers and skirts, which have none);
3. `Season` nodes hold overlapping warmth windows, and the Cypher query in
   `graph.infer_weather` returns every season the garment falls into.

Change a number in `config.py`, re-run `python cli.py seed`, and every garment
already in the database answers differently. That is the argument for a
knowledge graph over a wider classifier: the model is not retrained, the
knowledge is.

Try it in the Neo4j browser:

```cypher
MATCH (g:Garment)-[:MADE_OF]->(m:Material)
MATCH (g)-[:HAS_CATEGORY]->(c:Category)
MATCH (s:Season) WHERE g.warmth >= s.warmth_min AND g.warmth <= s.warmth_max
RETURN g, m, c, s
```

## Datasets

```bash
python scraper.py datasets                       # Fashionpedia (train2020.zip is 3.3GB)
python scraper.py fashion-mnist                  # Zalando Fashion-MNIST from Kaggle
python scraper.py fashion-mnist --export         # + write PNGs, one folder per class
python scraper.py fashion-mnist --export --limit 500 --size 224
```

Fashion-MNIST lives on Kaggle, so it needs an API token: kaggle.com → profile
picture → Settings → API → **Create New Token**, then drop `kaggle.json` in
`%USERPROFILE%\.kaggle\`. `KAGGLE_USERNAME` + `KAGGLE_KEY` work too.

`--export` turns the pixel CSV into real image files:

```
data/fashion_mnist/images/train/<class>/00042.png
```

10 classes: tshirt_top, trouser, pullover, dress, coat, sandal, shirt, sneaker,
bag, ankle_boot. `--size 224` upscales for CLIP, but 28×28 grayscale carries no
material, colour or texture, so it can only ever validate the *category* branch
of the pipeline. Fashionpedia is the dataset that matches the attributes this
project predicts.

## Project layout

```
scraper.py           dataset downloader / scraper (existing)
cli.py               command-line entry point
config.py            Neo4j creds + CLIP model + labels + warmth tables
pipeline/
  remove_bg.py       rembg background removal
  classify.py        CLIP zero-shot tagging
  weather.py         warmth scoring (the non-visual part)
  graph.py           Neo4j read/write + season inference
docker-compose.yml   Neo4j service
```

## Roadmap

1. ✅ CLI: analyze + store + query
2. ✅ Weather inference through the graph
3. Evaluation script: CLIP vs Fashionpedia labels (thesis metric)
4. Optional fine-tuning if zero-shot is weak (research only)
5. Conversational layer: LLM → Cypher over the graph
6. Frontend (Streamlit)
