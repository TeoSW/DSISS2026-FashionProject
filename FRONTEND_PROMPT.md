# Front end

**The app described below is built and lives in `frontend/`.** This file is the
requirements document it was written against, kept because a specification that
predates the code is worth more in a thesis than one reconstructed from it.

```bash
uvicorn api:app --port 8000                  # terminal one
cd frontend && npm install && npm run dev    # terminal two
```

`http://localhost:8000/docs` is the live contract. If it does not open, the app
has nothing to talk to and will say so on its own.

**Serving it from anywhere other than localhost.** A page on a public HTTPS
address cannot call `http://localhost:8000` on your machine without permission,
and when the browser refuses, the console says "failed to fetch", which looks
like a bug in the app and is not. `api.py` already answers Chrome's
private-network preflight, which removes one of the two obstacles; the other is
HTTPS itself. Put the backend behind a tunnel and point the app at it:

```bash
cloudflared tunnel --url http://localhost:8000
```

then set `VITE_API_URL` to the address it prints (see `frontend/.env.example`).
Running both on localhost, which is what `npm run dev` does, avoids the problem
entirely and is the right setup while building and for the defence.

---

## The requirements

Build a single-page React app called **Fitting Room** for a garment recognition
system. A person uploads one photo of one piece of clothing; the app sends it to
a Python backend that runs a vision-language model, and shows what came back.

The app never guesses and never classifies anything itself. Every label,
number and season on screen comes from the API. If the backend is down, say so
plainly rather than showing an empty or fake result.

### The API it talks to

Base URL comes from `VITE_API_URL`, defaulting to `http://localhost:8000`. Put
it in `.env` and read it through `import.meta.env`, never hardcoded in a
component.

**`GET /health`** — call once on mount to show connection state.

```json
{ "ok": true, "model": "patrickjohncyh/fashion-clip", "neo4j": true }
```

**`POST /analyze`** — `multipart/form-data` with `file` (the image), `save`
(`"true"` or `"false"`), `cutout` (`"true"`), and an optional `brand` string.

One photo can hold several garments, so the response is a **list**. The cloth
model segments upper / lower / full body and each region that carries something
is analysed on its own.

```json
{
  "analysis_id": "a1b2c3d4e5f6",
  "count": 2,
  "brand": "Nike",
  "garments": [
    {
      "analysis_id": "1dc75ef49050",
      "id": "6e942cce6f50",
      "region": "upper",
      "tags": {
        "category": { "label": "shirt",        "confidence": 0.522 },
        "material": { "label": "silk",         "confidence": 0.675 },
        "color":    { "label": "green",        "confidence": 0.993 },
        "sleeve":   { "label": "short sleeves", "confidence": 0.963 }
      },
      "warmth": 4,
      "layer": "base",
      "seasons": [ { "name": "warm", "temp_range": "18-25 C" } ],
      "summary": "green silk shirt, short sleeves",
      "cutout": "data:image/png;base64,...",
      "saved": false,
      "coverage": 0.218,
      "brand": "Nike",
      "price": 77.0,
      "price_estimate": { "tier": "premium", "known": true, "basis": "Nike is premium-tier; shirt base 35 €" }
    }
  ]
}
```

The top-level `analysis_id` identifies the whole upload; each garment has its
**own** `analysis_id`, which is the handle `/feedback` takes for that garment.
Per garment: `id` is `null` and `saved` is `false` when `save` was false;
`region` is `upper` / `lower` / `full`; `cutout` is that garment's own
background-removed image; `coverage` is how much of the frame it filled; `price`
is `null` unless a brand was given, and `price_estimate` is present only when the
price was guessed from the brand. Render each garment as its own result. When
`count` is 1, it is still a list of one.

Error responses are `{ "detail": "..." }` with status 400 (empty upload), 413
(over 12MB), 415 (not a readable image) or 503 (database write failed). Show
`detail` to the user as written; it is already phrased for a person.

**`GET /ontology`** — the label vocabulary and the warmth tables. Fetch once and
use it to explain answers. Never hardcode a copy of these lists.

```json
{
  "attributes": { "category": ["t-shirt", "shirt", "..."], "material": ["cotton", "..."] },
  "seasons": [ { "name": "hot", "temp_range": "above 25 C", "warmth_min": 1, "warmth_max": 3 } ],
  "material_warmth": { "linen": 1, "wool": 5 },
  "category_warmth": { "coat": { "warmth": 5, "layer": "outer" } },
  "sleeve_modifier": { "sleeveless": -1, "short sleeves": 0, "long sleeves": 1 }
}
```

**`POST /feedback`** — JSON in, what changed out. `verdict` is `"correct"` or
`"wrong"`; `corrections` maps an attribute group to the label it should have
been, and every value is checked against `/ontology` server side, so an invented
label comes back as a 400 with the list of legal ones in `detail`.

```json
{
  "analysis_id": "1dc75ef49050",
  "verdict": "wrong",
  "corrections": { "material": "cotton" },
  "note": "it is a cotton jersey, not knit"
}
```

```json
{
  "id": "6dd522e3a38d",
  "verdict": "wrong",
  "corrections": { "material": "cotton" },
  "warmth": 3,
  "layer": "full",
  "seasons": [ { "name": "hot", "temp_range": "above 25 C" } ],
  "graph_updated": true,
  "garment_updated": true,
  "corpus_size": 12
}
```

`warmth`, `layer` and `seasons` are the garment re-derived from the corrected
facts, so the result panel updates from this response without re-analysing the
photo. `garment_updated` is false when the garment was never saved: the
correction is still recorded, there is simply no stored node to re-point. The
analysis is only correctable while the server still remembers it (the last 32);
after that `/feedback` answers 404 and says to analyse the photo again.

**`GET /feedback/stats`** — the corpus counts and the confusion table, from both
the JSONL file and the graph.

**`GET /garments?material=cotton`** or `?season=cold`, `?category=`, `?style=`,
`?color=`, `?sleeve=` — exactly one filter per call.

```json
{ "filter": { "material": "cotton" }, "results": [ { "id": "6e942cce6f50" } ] }
```

**`GET /wardrobe`**, optionally `?region=upper|lower|full|unplaced` — everything
stored, with the fields a card needs. `region` is answered by traversing
`(Garment)->(Category)-[:WORN_ON]->(Region)`, so it is a graph question and not
a filter the browser could have applied itself.

```json
{
  "region": "upper",
  "regions": { "upper": 6, "lower": 2, "full": 1 },
  "count": 6,
  "items": [
    {
      "id": "236ae8f50598",
      "category": "hoodie", "region": "upper", "material": "cotton",
      "color": "black", "sleeve": "long sleeves", "style": "casual",
      "warmth": 7, "layer": "mid",
      "category_confidence": 0.62, "corrected": true,
      "seasons": [ { "name": "mild", "temp_range": "10-18 C" } ],
      "photo_url": "/garments/236ae8f50598/image",
      "created_at": "2026-07-24T19:41:02Z"
    }
  ]
}
```

`corrected` is true when a person overwrote any of its attributes; mark those
cards. `photo_url` is null for garments stored before pictures were kept, which
is a real state and needs its own wording, not a broken image.

**`GET /garments/{id}/image`** — the stored cutout as PNG, immutable and
cacheable for a year. **`DELETE /garments/{id}`** removes the garment, its edges
and its picture; 404 if it was never there. Any `Correction` about it survives on
purpose.

**`GET /insights`** — counts for the statistics section: `graph.by_category`,
`by_material`, `by_color`, `by_style`, `by_layer`, `by_season`, the `warmth`
histogram, `regions`, and `totals` (garments, mean warmth, mean confidence, how
many edges fall below 0.4, how many a person wrote). Plus `photos` (files and
bytes on disk) and the feedback summary.

**`GET /stats`** — `{ "nodes": { "Garment": 4, "Category": 12 }, "relationships": {...} }`.

### Screens

One page, three regions stacked, no routing.

**Drop area.** A large dashed target that accepts drag-and-drop, a click to open
the file picker, and paste from the clipboard. Show a preview of the chosen
image immediately, before any request. Accept `image/*` only, and reject over
12MB in the browser with the same wording the server uses, so the person is not
taught two different rules. A checkbox, off by default: "save this to the
knowledge graph".

**Result panel.** After a successful analyse, show:

- the background-removed cutout beside the original, so the removal is visible
- the summary sentence, large, as the headline answer
- the five attributes as rows: group name, label, and the confidence as a thin
  horizontal bar with the number beside it. Do not use a pie, a gauge or a
  radar. Confidence under 0.4 gets a muted "low confidence" marker, because the
  model is genuinely unsure there and the interface should not hide that.
- the warmth score as 3 of 11, with the layer named
- the seasons as chips, each showing the name and its temperature range

**Explain panel.** Below the result, a short block that says where the weather
answer came from, using the numbers from `/ontology`: material warmth plus
category warmth, adjusted for sleeves, matched against the season windows. Show
the actual arithmetic for this garment, for example "polyester 2 + t-shirt 1,
short sleeves 0, so 3 of 11". This is the point of the whole project and it
should be visible, not buried.

**Correction.** Under the result, two buttons: "yes, it is right" and "no, fix
it". The first posts a `correct` verdict straight away, because a confirmation
is signal too and should cost one click. The second opens a form with one select
per attribute group, built from `/ontology` and preselected to what the model
answered, plus a free-text note for the case where none of the labels fit. Only
the groups that actually changed are sent.

If the garment was never saved, a correction files it: the response comes back
with `filed: true` and a `garment_id`, and it appears in the wardrobe under the
label the person gave, not the one the model guessed. Reflect that in the result
panel, which is no longer showing an unsaved analysis.

Afterwards, show a receipt that states literally what happened: which label
became which, whether the graph accepted it, whether the stored garment was
re-derived and what its new warmth is, and how many judged analyses the corpus
now holds. Do not animate a progress bar suggesting the model just learned
something. It did not; the graph changed and the corpus grew, and the receipt
should say exactly that.

**Wardrobe.** What is stored, drawn as a wardrobe rather than listed as a table.
A rail per part of the body, cards hanging from it, and on each card the garment
photograph, because `e0c5053d68ee` tells a person nothing. Keep the id on the
card in small type: it is what the graph calls this thing, and hiding it makes
the two views impossible to line up.

Beside the rails, a tailor's dummy with clickable zones. Clicking the torso
shows what is worn on the upper body, the legs the lower, and the dress form
next to it the full-length rail; each zone carries its count and toggles off
when clicked again. Do not stack a third zone on top of the first two, and do
not navigate away: the rails are already below the figure, so bring them into
view.

Every card can be removed. Two clicks, the button becoming its own confirmation,
no modal dialogue: stealing focus to ask "are you sure" about one garment is
heavier than the action deserves. After a delete, the rails, the dummy's counts
and the statistics all have to reflect it without a page reload.

Empty is a normal state, per rail and overall, and says so plainly.

**Statistics.** Counts over what is stored: per category, material, colour,
style and layer, a histogram of the warmth scores across the 1 to 11 scale,
season coverage, mean confidence with the number of edges below 0.4, how many
attributes a person overwrote, and the confusion table from `/feedback/stats`.

Every chart here has a single series, so use one accent colour and let the
labels do the identifying; six hues for six bars of the same measurement is
decoration pretending to be information. The one exception is the colour
breakdown, where a swatch is legitimate because the label *is* a colour.

State clearly, in the panel itself, that none of this is accuracy. It describes
the contents of one wardrobe. Accuracy needs labelled ground truth and lives in
`evaluate.py`, and a large confident number in a UI is exactly how the two get
confused.

### States that must exist

- **connecting** — before `/health` answers
- **backend down** — `/health` failed. Explain that `uvicorn api:app --port 8000`
  is not running, and keep the drop area disabled.
- **analysing** — the first request of a session takes 20 to 40 seconds, because
  the model weights load on demand; later ones take about 3. Say that, honestly:
  "loading the model, this happens once" for the first, "analysing" after. A
  spinner with no words will read as a hang.
- **error** — show `detail`, keep the chosen image, let them retry without
  re-picking the file
- **graph unreachable** — `/health` returns `neo4j: false`. Analysis still works,
  so disable only the save checkbox and the library, and say why.

### Design

Cool near-neutral greys with a slight blue bias, one accent, generous
whitespace, and a clear type hierarchy. The image and the answer are the two
loud things; everything else recedes. Not a dashboard, not a marketing page: it
should feel like a good measuring instrument.

Numbers use a monospaced face and `tabular-nums` so columns line up. Confidence
bars are thin, 6 to 8 pixels, square at the baseline and rounded at the tip.

Full keyboard support: the drop area is focusable and takes Enter or Space,
focus rings are visible, the file input is reachable. Respect
`prefers-reduced-motion`. Support light and dark, and make the dark theme a
designed variant rather than an inversion.

### Do not

- do not invent labels, categories or materials the API did not return
- do not run any model in the browser or add a second AI service
- do not add login, accounts or a database of your own
- do not round a confidence up to make it look better, and do not hide a low one
- do not use emoji as icons
- do not let a correction be typed freely into the label fields; the vocabulary
  is whatever `/ontology` returns, and anything else belongs in the note
- do not claim the model improved because somebody pressed a button
