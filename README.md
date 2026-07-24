# DSISS-2026-Code

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Clothing recognition pipeline: photo → background removal → CLIP tags → Neo4j knowledge graph.
CLI first, frontend later.

## Stack & licenses (commercial-clean path)

| Piece | Role | License |
|-------|------|---------|
| rembg + U2Net | background removal | MIT / Apache 2.0 |
| CLIP / FashionCLIP | zero-shot tagging | MIT |
| transformers, torch, neo4j driver | runtime | Apache 2.0 / BSD-3 |
| Neo4j Community | knowledge graph | GPLv3, see note below |
| Fashion-MNIST | baseline dataset | MIT |
| Fashionpedia | **eval / research only** | annotations CC-BY 4.0; images = 3rd-party |

The commercial product runs **zero-shot on the user's own images**, nothing is trained on
Fashionpedia images, so there is no image-licensing risk. Fashionpedia is used only to measure
accuracy in the thesis.

**On the GPLv3 in that table:** this project talks to Neo4j over the Bolt network protocol,
through a driver that is Apache 2.0. Two separate processes, no linking, and the server is
never redistributed here (`docker-compose.yml` pulls the official image). The GPL therefore
does not reach this code, which is why it can be MIT. Bundling and shipping the Neo4j
Community binaries inside a product would be a different question.

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

Neo4j browser: http://localhost:7474. The user is always `neo4j` and the password
is whatever `NEO4J_PASSWORD` says in your `.env`; the compose file reads the same
variable, so the container and the Python driver cannot disagree.

Community edition has a single built-in account. Putting any other name in
`NEO4J_AUTH` makes the server refuse to start with *"Invalid admin username, it
must be neo4j"*, because `CREATE USER` and role management are Enterprise
features. `NEO4J_AUTH` is also read only while `./neo4j_data` is empty, so on a
database that already exists the password is changed with Cypher instead:

```cypher
ALTER CURRENT USER SET PASSWORD FROM 'old' TO 'new'
```

## Use the CLI

```bash
python cli.py test-db                     # check the DB connection
python cli.py seed                        # load the ontology (once, and after editing config.py)
python cli.py stats                       # node / relationship counts
python cli.py analyze photo.jpg           # background removal + tags + weather
python cli.py analyze photo.jpg --save    # also store in Neo4j
python cli.py analyze photo.jpg --json    # raw JSON instead of the summary
python cli.py analyze photo.jpg --save --dataset fashionpedia   # record where the image came from
python cli.py query --material cotton     # list stored garments by attribute
python cli.py query --season cold         # list stored garments by weather
```

`test-db`, `seed`, `stats` and `query` only need the `neo4j` driver; torch and
rembg are imported inside `analyze`, so the database side works before the ~2.5GB
of ML dependencies finish installing.

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

1. every `Material` and `Category` node carries a warmth weight (1-5), seeded
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

## What is actually in the graph

`python cli.py seed` writes 57 nodes and 20 relationships, before a single photo
is analyzed:

```
Category 12   Material 8   Style 6   Color 10   Sleeve 3
Season 5      Dataset 3    DatasetClass 10
COLDER_THAN 4   HAS_CLASS 10   MAPS_TO 6
```

Two halves. Category, Material and Season carry the warmth weights that answer
the weather question described above. The rest records what `scraper.py` can
fetch and what may legally be done with it:

```
(Dataset {license, usage}) -[:HAS_CLASS]-> (DatasetClass) -[:MAPS_TO]-> (Category)
(Garment) -[:FROM_DATASET]-> (Dataset)
```

Fashion-MNIST is MIT and may be trained on; Fashionpedia images belong to third
parties and are evaluation-only; anything the scraper crawls carries unknown
terms. Storing that as data rather than as a paragraph means a garment can be
asked where its picture came from:

```cypher
MATCH (g:Garment)-[:FROM_DATASET]->(d:Dataset)
RETURN g.id, d.title, d.usage
```

Six of the ten Fashion-MNIST classes map onto a category this project predicts.
The other four are left dangling on purpose, and one query says how far the
baseline dataset covers this ontology:

```cypher
MATCH (k:DatasetClass) WHERE NOT (k)-[:MAPS_TO]->() RETURN k.class_name
// ankle_boot, bag, sandal, sneaker: footwear and accessories, out of scope
```

## Evaluation

```bash
python scraper.py datasets --val-only    # 240MB, skips the 3.2GB training split
python evaluate.py --limit 200           # quick run
python evaluate.py --json results/run.json  # the whole validation split
python evaluate.py --model openai/clip-vit-base-patch32   # compare checkpoints
python evaluate.py --no-aliases          # only the 12 ontology labels
python evaluate.py --prompt-ensemble     # average the six templates
python evaluate.py --two-stage mass      # region first, then category
python evaluate.py --remove-bg           # with the rembg step
python evaluate.py --split dev           # the half you are allowed to tune on
```

Fashionpedia annotates every garment in a photo with a box and a category. Each
box is cropped and classified on its own, so this measures the classifier and
not a detector: the pipeline is told where the garment is, which is the fair
comparison because in the product the user photographs one item.

### What the report prints

```
1961 instances, patrickjohncyh/fashion-clip
  flat category, single prompts, aliases on, background removal off
  top-1 accuracy       63.3%   (1242/1961)
  top-3 accuracy       88.4%
  majority baseline    25.9%   (always answer 'dress')
  chance                8.3%   (12 classes)

per class
  label      support  recall  precision      F1
  dress          508   73.0%      82.8%   0.776
  ...
  macro         1961   60.8%      55.4%   0.557
```

Two baselines, because one of them flatters. Chance across twelve classes is
8.3%, but the split is unbalanced enough that answering "dress" every single time
scores 25.9%, and that is the number any result has to beat before it means
anything.

The `macro` row averages across classes without weighting by support, so
`hoodie` with 7 instances counts as much as `dress` with 508. Top-1 can be
carried by the two largest classes alone; macro F1 cannot, which makes it the
figure to quote for a set this skewed. Both go into the `--json` file, along with
the per-class breakdown, the confusion pairs and the exclusions, so the numbers
in this README can be regenerated rather than trusted.

Every run quoted below is kept in [`results/`](results/), which is versioned on
purpose: `data/` is gitignored because it holds the Fashionpedia images, and
clearing it must not take the thesis numbers with it.

Every flag above is an experiment that was run, and each is written up below
with its numbers:

| change | verdict | top-1 |
|---|---|---|
| starting point, ViT-B/32, 12 labels | | 49.0% |
| FashionCLIP instead | kept, now the default | 59.4% |
| wider label vocabulary on top | kept, now the default | 63.3% |
| prompt ensembling | rejected | 58.6% |
| two-stage by region | rejected | 62.7% on a subset |
| background removal | no effect, kept for the product | 49.3% on a subset |

Two of five helped. The three that did not are still in the code as flags,
because a claim that something does not work needs the number that says so.

The rows are cumulative, which is why ViT-B/32 appears here at 49.0% and at
49.1% in the checkpoint table below. The first is the original twelve-label
setup, the second is ViT-B/32 re-run with the wider vocabulary so that all three
checkpoints are measured under identical conditions. The 0.1 between them is the
whole effect of the vocabulary on that model, and it is the point of the
paragraph after next.

The two that helped do not stack evenly. On ViT-B/32 the wider vocabulary is
worth +0.1 top-1 and +9.8 top-3; on FashionCLIP it is worth +3.9 and +6.8. A
model that already knows the difference between a top and a blouse can use the
extra words, and one that does not simply reshuffles its ranking below the
winner.

### Which checkpoint

Three checkpoints, all zero-shot, all on the full 1961-instance validation split,
all with the wider vocabulary on, one template, no background removal, the same
crops. The only thing that differs is the weights:

| model | params | trained on | top-1 | top-3 | macro F1 |
|---|---|---|---|---|---|
| openai/clip-vit-base-patch32 | 151M | general web | 49.1% | 80.4% | 0.446 |
| openai/clip-vit-large-patch14 | 428M | general web | 48.7% | 80.9% | 0.437 |
| patrickjohncyh/fashion-clip | 151M | 800K fashion pairs | **63.3%** | **88.4%** | **0.557** |

This is as close to a controlled experiment as the project gets, because
FashionCLIP is not a different architecture. It is the same ViT-B/32 vision
tower, the same 151M parameters, the same 224px input, further trained on
fashion. So the table isolates one variable at a time:

- **more parameters, same data**: 151M to 428M, and top-1 moves by -0.4 points
- **same parameters, fashion data**: +14.2 points

Scale bought nothing on this task and domain bought everything. That is also the
cheap answer to "should we fine-tune": someone already did, on 800K pairs no
student has access to, and released the weights under MIT.

The parameter counts are not quoted from the model cards, they are counted:

```python
from transformers import CLIPModel
m = CLIPModel.from_pretrained("patrickjohncyh/fashion-clip")
sum(p.numel() for p in m.parameters())          # 151M
m.config.vision_config.hidden_size, m.config.vision_config.num_hidden_layers
m.config.vision_config.patch_size                # 768, 12, 32 -- a ViT-B/32
```

ViT-L/14 is not merely equal, it fails differently. Its recall collapses on
`jacket` (16.4%) and `trousers` (35.6%) while `shorts` reaches 100% precision on
34.6% recall: a model answering rarely but confidently. Averaged out, that lands
in the same place as ViT-B/32 by a different route.

FashionCLIP is therefore the default in `config.py`. Note what that changes in
the licensing story: the pipeline still trains on nobody's images, but it now
depends on weights that its authors trained on an 800K-pair Farfetch catalogue.
The MIT licence covers the weights; the argument is now about someone else's
training data rather than about ours.

### Giving CLIP more words than the ontology has

The ontology has twelve categories because the warmth tables are built on twelve.
CLIP does not have to be offered only twelve words. Its worst class was
`t-shirt`, at 22.0% recall against 91.7% precision: it almost never said
"t-shirt" wrongly, and almost never said it at all. A tank top has nowhere to go
in a twelve-word vocabulary, so the model picks whatever else is close.

`CATEGORY_ALIASES` widens the vocabulary to nineteen words and folds the answer
back afterwards, adding the probabilities of the aliases onto their ontology
label, because "top" and "tank top" are two ways of scoring the same answer. The
graph still only ever sees the twelve.

| | top-1 | top-3 | `t-shirt` recall |
|---|---|---|---|
| 12 labels | 59.4% | 81.6% | 22.0% |
| 19 labels, folded | **63.3%** | **88.4%** | **54.5%** |

Four points overall and the worst class more than doubled, for seven lines of
configuration and no retraining. This is the cheapest gain in the whole project,
and it says something worth putting in the thesis: a zero-shot classifier's
label set is a design choice, not a property of the model, and forcing it to
match the storage schema costs accuracy for no reason.

### The number

1961 instances, the whole validation split, FashionCLIP, aliases on, zero-shot:

| | final | FashionCLIP alone | ViT-B/32 |
|---|---|---|---|
| top-1 accuracy | 63.3% | 59.4% | 49.0% |
| top-3 accuracy | 88.4% | 81.6% | 70.6% |
| majority baseline | 25.9% | 25.9% | 25.9% |
| mean confidence | 0.75 (0.83 right, 0.61 wrong) | 0.76 (0.84 / 0.65) | 0.48 (0.56 / 0.41) |

Confidence separates right from wrong answers by 0.21, enough to build a "not
sure" threshold on. Per class, the starting point against where it ended up:

| label | support | recall | precision | F1 |
|---|---|---|---|---|
| `dress` | 508 | 68.5% → 73.0% | 65.0% → 82.8% | 0.667 → 0.776 (+0.109) |
| `t-shirt` | 451 | 10.4% → 54.5% | 87.0% → 71.3% | 0.186 → 0.618 (+0.432) |
| `trousers` | 205 | 61.5% → 69.8% | 66.7% → 82.7% | 0.640 → 0.757 (+0.117) |
| `skirt` | 160 | 73.1% → 69.4% | 29.8% → 57.2% | 0.423 → 0.627 (+0.204) |
| `jacket` | 116 | 62.9% → 39.7% | 39.5% → 61.3% | 0.485 → 0.482 (-0.003) |
| `jeans` | 108 | 48.1% → 81.5% | 69.3% → 72.7% | 0.568 → 0.769 (+0.200) |
| `shorts` | 104 | 69.2% → 73.1% | 51.4% → 79.2% | 0.590 → 0.760 (+0.170) |
| `coat` | 104 | 46.2% → 47.1% | 48.5% → 51.6% | 0.473 → 0.492 (+0.020) |
| `shirt` | 98 | 11.2% → 44.9% | 50.0% → 26.8% | 0.183 → 0.336 (+0.153) |
| `blazer` | 67 | 67.2% → 61.2% | 21.7% → 37.6% | 0.328 → 0.466 (+0.137) |
| `sweater` | 33 | 51.5% → 72.7% | 34.7% → 18.8% | 0.415 → 0.298 (-0.116) |
| `hoodie` | 7 | 57.1% → 42.9% | 30.8% → 23.1% | 0.400 → 0.300 (-0.100) |
| **macro** | 1961 | | | **0.447 → 0.557 (+0.110)** |

Read the recall column alone and four classes look damaged. The F1 column is
there because three of those four are not.

`jacket` is the clearest case: 23 points of recall lost, 22 of precision gained,
F1 unchanged at 0.48. The old model answered "jacket" for almost anything with
sleeves, which flatters recall and is why its precision was 39.5%. The new one
is more selective. Nothing improved and nothing broke; the class moved along its
own trade-off curve. `skirt` and `blazer` lost recall and gained far more
precision, so their F1 rose by 0.20 and 0.14.

Two classes did get worse. `hoodie` moved on seven instances, which is noise and
should be quoted as such. `sweater` is real: F1 down 0.116, because the aliases
fold both "sweatshirt" and "cardigan" onto it, and the model now over-predicts
it. Precision fell from 34.7% to 18.8%. That is the price of the vocabulary
change, paid by one class of 33 instances to gain 0.43 F1 on a class of 451.

Macro F1 is the honest headline for a set this unbalanced, since `dress` and
`t-shirt` are half the data and top-1 can be carried by them alone. It went from
0.447 to 0.557.

The floor is now the outerwear: `jacket` and `coat` sit at 0.48 and 0.49 F1.
Those two differ mostly by length, in a box that often cuts the hem off.

### The dev / test split, frozen before fine-tuning

```bash
python make_split.py                 # once, writes splits/fashionpedia_val.json
python make_split.py --show          # print it
python evaluate.py --split dev       # while you are still making choices
python evaluate.py --split test      # once, at the end
```

Every number above was measured on all 1961 instances, which was fine while the
only decisions were a checkpoint and a word list. It stops being fine the moment
fine-tuning starts: a score you have optimised against is not an estimate of
anything. So the validation set is cut in two and half of it is put away.

| | images | garments |
|---|---|---|
| dev | 684 | 1177 |
| test | 458 | 784 |

The unit is the image, not the garment. Fashionpedia photos carry several
annotated garments each, and two crops of the same photo share the person, the
lighting and usually the outfit; splitting by instance would put near-duplicates
on both sides and inflate the test score.

The assignment is stratified and greedy rather than random, because `hoodie` has
seven instances in the whole set and a coin flip can leave one side with none.
Images go one at a time to whichever side is furthest below its quota for the
rarest class they contain. Every class lands within 0.6 points of the 60% target,
`hoodie` included, at 4 against 3.

The same pipeline, unchanged, scores:

| | top-1 | top-3 | macro F1 |
|---|---|---|---|
| dev | 63.2% | 87.9% | 0.560 |
| test | 63.5% | 89.0% | 0.557 |
| all 1961 | 63.3% | 88.4% | 0.557 |

The halves agree to within 0.3 points, which is the evidence that the split is
representative rather than a lucky cut.

**What this does not fix.** The zero-shot configuration was already chosen by
looking at all 1961 instances, so the test half is not clean with respect to the
checkpoint and the vocabulary. It is clean from here on, which is what
fine-tuning needs. The thesis should say exactly that rather than implying a
purity these numbers do not have.

`make_split.py` refuses to overwrite an existing split, because a split is only
worth anything if it never moves.

What remains of the `t-shirt` error is the mapping, and belongs in the caveats
rather than in the model's column. Fashionpedia's class 1 is "top, t-shirt,
sweatshirt", one label for a tank top, a crop top and a sweatshirt, all scored
here as `t-shirt`. When the pipeline answers `sweater` for a sweatshirt it is
counted wrong, which is a limitation of the comparison and not of the answer.

### Two-stage classification, rejected

The largest error group was garments read as belonging to the opposite half of
the body, so the obvious fix was to ask which half first and then choose only
among the categories that live there. `--two-stage` implements it two ways:
`prompt` asks CLIP directly with the sentences in `REGION_PROMPTS`, `mass` sums
the category probabilities already falling in each region. Same 300 instances:

| | top-1 | top-3 | region correct |
|---|---|---|---|
| flat | 63.0% | 84.7% | 80.3% |
| two-stage, prompt | 53.3% | 69.7% | 77.0% |
| two-stage, mass | 62.7% | 75.3% | 82.0% |

Neither beats the flat classifier, on either checkpoint. Asking for the region
directly is worse at it than the category head is by accident: a flat answer
already implies a region, and it gets that region right 80% of the time without
being asked. Deciding the region first only adds a second place to be wrong,
and it caps top-3 at the size of one region.

The code is kept because the negative result is worth reporting and the region
accuracy is a useful diagnostic on its own.

### Prompt ensembling, also rejected

CLIP is famously sensitive to phrasing, and the standard remedy is to embed each
label under several templates and average the vectors. `PROMPT_TEMPLATES` holds
six, `--prompt-ensemble` turns the averaging on. On the full validation split it
scored 58.6% against 59.4% for the single template.

It does not fail evenly, which is the interesting part: `shirt` gained six points
and `coat` nine, while `t-shirt` lost seven. Averaging six sentences moves
accuracy between classes rather than adding any, so it is off by default.

### Does background removal help?

`--remove-bg` runs the same rembg step the CLI pipeline uses. On the same 300
instances, same seed, measured on ViT-B/32 before the switch to FashionCLIP:

| | top-1 | top-3 | mean confidence |
|---|---|---|---|
| crop only | 52.0% | 75.7% | 0.486 |
| crop + rembg | 49.3% | 72.7% | 0.465 |

Three points lower, which on 300 instances is inside the noise, so the honest
reading is that background removal buys nothing here rather than that it hurts.
It costs about 1.5 seconds per image, roughly fifty times the classification
itself.

That is a statement about this dataset, not about the product. Fashionpedia
photos are street and editorial shots, and a box drawn tightly around a garment
already contains little background to remove. A user photographing a coat on a
bed or against a wall is the case rembg was put there for, and this experiment
does not measure it.

What cannot be measured: Fashionpedia's 294 attributes cover silhouette,
neckline, length, pattern, opening, waistline, non-textile materials and 153
style nicknames, and not one of them names a textile fibre. There is no ground
truth for cotton, wool or denim in this dataset, so the material branch, and the
warmth score that depends on it, is unvalidated. `evaluate.py` prints the
predicted material distribution instead, which shows the model leans towards
`polyester` (26%) and almost never says `cotton` (1.3%), but proves nothing
about accuracy.

## Fine-tuning

```bash
python scraper.py datasets                    # now the full set, train2020.zip is 3.2GB
python finetune.py --epochs 3
python evaluate.py --model models/finetuned --split dev
```

The text tower and the logit scale are frozen and the label prompts stay the
ones in `config.py`, so only the vision tower moves. That keeps the zero-shot
interface intact: the result is written with `save_pretrained`, and
`evaluate.py --model models/finetuned` reads it back with no changes at all.
Nothing about the measurement differs between the zero-shot run and the
fine-tuned one except the weights, which is the same discipline the checkpoint
comparison used.

The model is trained against the twelve ontology labels while still being
offered the nineteen-word vocabulary: the classifier head is built by averaging
each label's aliases into one vector. Training it on twelve while serving it
nineteen would teach it a task it is never asked at inference.

**On the licence, plainly.** This trains on Fashionpedia images, which belong to
third parties and are published for research. The resulting weights are a thesis
artifact: not shipped, not redistributed, not what the product runs. The product
stays zero-shot on FashionCLIP, whose MIT weights someone else trained on data
they had rights to. Those are two different claims and the thesis should not
blur them.

Fashion-MNIST is the alternative that is MIT and freely trainable, and it is not
used here: 28x28 grayscale carries no material, colour or texture, so it can
teach the model nothing about the attributes this pipeline predicts, and only
six of its ten classes map onto this ontology at all.

Checkpoints land in `models/`, which is gitignored at roughly 600MB each.

Measure on `--split dev`. The test half is for one run at the end.

### What it bought

Two epochs over all 74159 training crops, batch 32, lr 1e-5 cosine-annealed,
13.5 minutes on an RTX 5060 laptop. Measured on the dev half, against the frozen
zero-shot baseline:

| | zero-shot | fine-tuned | |
|---|---|---|---|
| top-1 | 63.2% | **80.5%** | +17.3 |
| top-3 | 87.9% | **96.3%** | +8.4 |
| macro F1 | 0.560 | **0.673** | +0.113 |
| mean confidence | 0.755 | 0.868 | |
| body region correct | 85.1% | 93.1% | |

| label | support | recall | precision | F1 |
|---|---|---|---|---|
| `dress` | 305 | 72.8% → 87.5% | 81.9% → 89.9% | 0.771 → 0.887 (+0.116) |
| `t-shirt` | 271 | 55.7% → 86.3% | 72.2% → 81.0% | 0.629 → 0.836 (+0.207) |
| `trousers` | 123 | 69.1% → 88.6% | 85.0% → 80.7% | 0.762 → 0.845 (+0.083) |
| `skirt` | 96 | 69.8% → 76.0% | 58.3% → 83.9% | 0.635 → 0.798 (+0.163) |
| `jacket` | 70 | 42.9% → 71.4% | 62.5% → 72.5% | 0.508 → 0.719 (+0.211) |
| `jeans` | 65 | 83.1% → 70.8% | 75.0% → 93.9% | 0.788 → 0.807 (+0.019) |
| `coat` | 62 | 45.2% → 59.7% | 50.9% → 78.7% | 0.479 → 0.679 (+0.200) |
| `shorts` | 62 | 72.6% → 91.9% | 73.8% → 90.5% | 0.732 → 0.912 (+0.180) |
| `shirt` | 59 | 42.4% → 81.4% | 26.3% → 56.5% | 0.325 → 0.667 (+0.342) |
| `blazer` | 40 | 55.0% → 40.0% | 36.1% → 76.2% | 0.436 → 0.525 (+0.089) |
| `sweater` | 20 | 65.0% → 55.0% | 15.5% → 31.4% | 0.250 → 0.400 (+0.150) |
| `hoodie` | 4 | 50.0% → 0.0% | 33.3% → 0.0% | 0.400 → 0.000 (-0.400) |
| **macro** | 1177 | 60.3% → 67.4% | 55.9% → 69.6% | **0.560 → 0.673 (+0.113)** |

Eleven of twelve classes improve on F1. The twelfth is `hoodie`, which has four
instances in dev and 411 in training; it went from getting two right to getting
none, and no conclusion of any kind should be drawn from that.

**Before believing any of it**, the two splits were checked for overlap by file
name in both directions: 45623 training images, 1158 validation images, zero in
common. A seventeen-point jump is exactly the result that deserves that check
before it deserves enthusiasm.

**More data stopped helping early.** The same recipe on 20000 crops instead of
74159 scores 79.8% and 0.662 macro F1, so 3.7 times the data bought 0.7 points.
What is left is not a data volume problem: `blazer` at 0.525 and `sweater` at
0.400 are confused with `jacket` and `coat`, garments that differ by cut and
length rather than by anything a 224px crop shows clearly.

**What fine-tuning did not touch.** Material, colour, style and sleeve are still
zero-shot, because Fashionpedia has no fibre labels to train them on. The warmth
score therefore rests on an unvalidated material prediction whatever the category
accuracy says, and the thesis should not let the headline number imply otherwise.

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
evaluate.py          CLIP vs Fashionpedia, the thesis metric
finetune.py          vision-tower fine-tuning (research only)
make_split.py        freezes the dev/test split, once
results/             every evaluation run, versioned (data/ is not)
splits/              the frozen dev/test assignment
config.py            Neo4j creds + CLIP model + labels + warmth + dataset tables
pipeline/
  remove_bg.py       rembg background removal
  classify.py        CLIP zero-shot tagging
  weather.py         warmth scoring (the non-visual part)
  graph.py           Neo4j read/write + season inference + ontology seeding
docker-compose.yml   Neo4j service (image pinned to 5.26-community)
```

## Roadmap

1. ✅ CLI: analyze + store + query
2. ✅ Weather inference through the graph
3. ✅ Dataset provenance in the graph (licence travels with the garment)
4. ✅ Evaluation script: CLIP vs Fashionpedia labels (thesis metric)
5. ✅ Five experiments: FashionCLIP and a wider label vocabulary won,
   two-stage classification, prompt ensembling and background removal did not
   (49.0% → 63.3%)
6. ✅ Dev/test split frozen before any training
7. Fine-tuning, now that the cheap levers are exhausted (research only, and
   the weights are never shipped)
6. Conversational layer: LLM → Cypher over the graph
7. Frontend (Streamlit)

## License

[MIT](LICENSE).

The datasets are not covered by it and keep their own terms:

- **Fashion-MNIST**, Xiao, Rasul & Vollgraf (2017), Zalando Research. MIT.
- **Fashionpedia**, Jia et al. (2020). Annotations CC-BY 4.0; the images belong to
  their respective owners, so they are used for evaluation only and are never
  redistributed from this repository (`data/` is gitignored).

`scraper.py` can also crawl product listings. It honours `robots.txt` and rate-limits
itself, but robots.txt is not a licence: whoever points it at a site is responsible for
that site's terms of service and for the copyright on the images it collects.
