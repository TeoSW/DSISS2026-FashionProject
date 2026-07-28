# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

**Primary: consumers who own clothes.** Ordinary people photographing their own
garments, building up a wardrobe, and deciding what to wear for the weather.
Confirmed 2026-07-27, and it is a deliberate reorientation: the system was built
in an academic setting (DSISS 2026) and much of the existing interface still
addresses an examiner rather than an owner. See the open decision under
Capabilities and Constraints.

**Secondary: the developer**, who also operates the system — running the CLI,
the evaluation harness and the fine-tuning, and reading the statistics page.
This audience is real but is not who the web app is being designed for.

The situation is domestic and unhurried: someone at home with a phone or a
folder of photos, one garment at a time, with no deadline and no expertise in
machine learning.

## Product Purpose

WRDB reports what a garment is — category, material, colour, style, sleeve —
from a single photo, then derives the weather it suits and keeps it in a
wardrobe the person can browse, correct, price and dress from.

Success is a person trusting the wardrobe enough to keep adding to it, and the
weather answer being one they would act on.

## Positioning

**The weather is derived, not predicted.** Material warmth plus category warmth,
adjusted for sleeves, matched against season windows held as `Season` nodes in
Neo4j and resolved by graph traversal. Two consequences a neighbouring product
built on a classifier alone could not truthfully copy:

- The reasoning can be changed without retraining. Edit a warmth weight in
  `config.py`, re-seed, and every garment already stored answers differently.
- A correction changes the answer immediately. Re-pointing an attribute edge and
  marking it `source: 'human'` moves the garment's warmth and its seasons in the
  same request, because inference reads the graph rather than the model.

The model is deliberately confined to what is visible in the photograph.
Everything inferential happens in the graph, where it can be inspected and
argued with.

## Operating Context

Runs locally, as three processes: Neo4j in Docker, a FastAPI backend, and a Vite
dev server. There is no deployment, no hosting and no multi-user story — every
install is one person on one machine, and the database is a bind-mounted folder
beside the repo.

Consequences that shape the experience and are facts, not preferences:

- The graph must be running for saving, the wardrobe, the recommender and the
  statistics. Analysis alone works without it.
- The first analysis of a session downloads roughly 600MB of model weights;
  later ones take seconds.
- Photos the user uploads are stored as background-removed cutouts under
  `data/wardrobe/`, which is gitignored and never leaves the machine.

## Capabilities and Constraints

Built and working: multi-garment segmentation from one photo; five attribute
groups with confidences; warmth on a 1–11 scale across five seasons; the
wardrobe organised by body region on a mannequin, where clicking a region is a
Cypher traversal rather than a browser-side filter; a correction loop; brand
price estimates with manual override; wash-care labels; real retailer shop
links; a gap analysis; and an admin statistics page.

Measured accuracy, reported in full in the README including the rejected
approaches: 49.0% top-1 zero-shot with general CLIP, 63.3% with FashionCLIP and
a wider vocabulary, 80.5% on dev after fine-tuning the vision tower.

Durable constraints:

- **Fifty-six categories across nine body regions**, covering clothing,
  footwear, headwear, accessories, jewellery and bags. Anything outside the
  ontology still cannot be labelled correctly, which is what the "something is
  missing" report exists to record.
- **Only clothing can be segmented.** `u2net_cloth_seg` returns three masks —
  upper body, lower body, whole body — and has never seen a shoe. Everything
  outside those three is found by a band crop or a whole-photo probe, both of
  which are weaker instruments, and a piece found by a probe has no picture of
  itself because nothing drew a box around it.
- **Neo4j Community has exactly one account**, always named `neo4j`. No user
  management, no roles. Any multi-user design would need a different edition.
- **Fashionpedia is evaluation-only.** Nothing shipped is trained on its images.
  Product features must not depend on it.
- **Corrections do not retrain the model.** The graph is fixed instantly; the
  model changes only when a batch is folded into a new checkpoint.

**Open decision — who the interface addresses.** The confirmed user is a
consumer, but the current build exposes an admin statistics page, a confusion
table, dataset provenance, per-attribute confidence percentages and evaluation
vocabulary. Whether these are hidden, relocated behind an operator view, or
reframed for an owner is undecided and should be settled before significant
interface work. Recorded, not resolved.

**Open decision — what happens after continued development.** Work continues
with no fixed external deadline and no committed deployment, distribution or
audience beyond the developer's own machine.

## Brand Commitments

- **WRDB** is the project name; the web app presents itself as **Fitting Room**,
  subtitled *garment · instrument*.
- **MIT licensed**, with a deliberately commercial-clean dependency path. Dataset
  terms are tracked separately and must not be blurred into it.
- The existing interface copy is plainly written, lower-case, and unusually
  precise about what the system does and does not know. This is observed in the
  build, not confirmed by the user as binding.

## Evidence on Hand

Real, in the repository, and usable without qualification:

- `results/*.json` — twelve evaluation runs including the rejected experiments
  (prompt ensembling, two-stage classification, background removal).
- `splits/fashionpedia_val.json` — the dev/test split, frozen before fine-tuning.
- `presentation/index.html` — a deck summarising the system.
- `README.md` — the full method, the numbers, and the dead ends.

Absences that future work must not fabricate: there are **no users other than
the developer**, no usage data, no testimonials, no customers, no pricing or
licensing model, no deployment, and no accuracy figure on the held-out test half
— that run is deliberately unspent. Prices shown for garments are labelled
estimates derived from brand, and retailer links are real; neither may be
presented as anything firmer.

## Product Principles

1. **Nothing is decided in the browser.** Every label, confidence, warmth number
   and season on screen came back from the API. The one deliberate exception is
   the derivation panel, which re-computes the warmth arithmetic from
   `/ontology` in order to show its working, and says so on screen when it
   disagrees with the server. *Confirmed binding by the user.*
2. **Inference belongs in the graph, not the model.** The model reports what is
   visible; the graph decides what it means. This is the product's mechanism and
   the reason its answers can be changed and argued with.
3. **A correction is the one moment the system knows for certain what it is
   looking at.** It is therefore never discarded — including when the garment was
   never saved, in which case the correction creates it.
4. **The consumer is the person being designed for**, even though the system was
   built to be examined. Where the two conflict, the owner of the clothes wins.

Three further behaviours are present in the current build and were **not**
confirmed as binding when offered: naming every loading and failure state
honestly; refusing to imply the model learns per click; and the licence-clean,
no-invented-data discipline. They are recorded here as observed practice so that
a future change to them is a decision rather than an accident.
