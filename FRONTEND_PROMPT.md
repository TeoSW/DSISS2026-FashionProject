# Front end

The React app is built separately, in Lovable, and talks to `api.py` over HTTP.
The prompt below is the whole brief: paste it into Lovable as the first message.

## Before you paste it

Start the backend first, so you can point the app at something real:

```bash
uvicorn api:app --port 8000
```

`http://localhost:8000/docs` is the live contract. If it does not open, the
prompt below has nothing to talk to.

**The part that catches everyone.** Lovable previews are served from an HTTPS
address on the public internet. Your backend is `http://localhost:8000`, on your
machine. A browser will not let a public page call your laptop without asking
first, and when it refuses, the console says "failed to fetch", which looks like
a bug in the app and is not.

Three ways out, in the order I would try them:

1. **Export the Lovable project to GitHub and run it locally** with `npm run dev`.
   Front end and backend are then both on localhost and nothing is blocked. This
   is the one to use while building.
2. **Put the backend behind a tunnel** for a demo you give from someone else's
   screen: `cloudflared tunnel --url http://localhost:8000` prints an HTTPS
   address; set `VITE_API_URL` to it.
3. Deploy the backend to a machine with a GPU. Only worth it after the thesis.

`api.py` already answers Chrome's private-network preflight, which removes one
of the two obstacles. The other one is HTTPS, and only a tunnel fixes that.

---

## The prompt

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
(`"true"` or `"false"`), `cutout` (`"true"`).

```json
{
  "id": "6e942cce6f50",
  "tags": {
    "category": { "label": "t-shirt",       "confidence": 0.658 },
    "material": { "label": "polyester",     "confidence": 0.718 },
    "style":    { "label": "casual",        "confidence": 0.615 },
    "color":    { "label": "blue",          "confidence": 1.0   },
    "sleeve":   { "label": "short sleeves", "confidence": 0.996 }
  },
  "warmth": 3,
  "layer": "base",
  "seasons": [
    { "name": "hot",  "temp_range": "above 25 C" },
    { "name": "warm", "temp_range": "18-25 C"    }
  ],
  "summary": "blue polyester t-shirt, short sleeves",
  "cutout": "data:image/png;base64,...",
  "saved": true
}
```

`id` is `null` and `saved` is `false` when `save` was false. `cutout` is the
photo with its background removed, ready to drop straight into an `<img src>`.
`warmth` is an integer from 1 to 11. `layer` is one of `base`, `mid`, `outer`,
`bottom`, `full`.

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
  "category_warmth": { "coat": { "warmth": 5, "layer": "outer" } }
}
```

**`GET /garments?material=cotton`** or `?season=cold`, `?category=`, `?style=`,
`?color=`, `?sleeve=` — exactly one filter per call.

```json
{ "filter": { "material": "cotton" }, "results": [ { "id": "6e942cce6f50" } ] }
```

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

**Library.** A filter row of chips built from `/ontology` (materials, seasons).
Clicking one calls `/garments` and lists what comes back. Empty is a normal
state and says "nothing stored with this filter yet", not an error.

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
