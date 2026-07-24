# Fitting Room

The web app for the garment recognition pipeline. React, TypeScript, Vite, no UI
framework and no state library: the whole thing is five components and one fetch
module, which is the right size for what it does.

```bash
npm install
npm run dev        # http://localhost:5173
```

It needs the backend running:

```bash
cd .. && uvicorn api:app --port 8000
```

If the backend is somewhere else, copy `.env.example` to `.env.local` and set
`VITE_API_URL`. That variable is read in one place, `src/api.ts`; no component
knows a URL.

## What is where

```
src/api.ts             every call to the backend, and the only URL in the app
src/types.ts           the shapes api.py returns, by hand, because they are small
src/App.tsx            connection state, the analysis flow, the five sections
src/components/
  Specimen.tsx         drag, click or paste one photo; size and type checked here
  Reading.tsx          the answer: cutout, attributes, confidences, warmth, seasons
  Flag.tsx             the correction loop, from the person's side
  Derivation.tsx       the warmth arithmetic, re-derived from /ontology and shown
  Wardrobe.tsx         stored garments on rails, with their photographs; delete
  Mannequin.tsx        the tailor's dummy: clicking a zone runs a graph traversal
  Insights.tsx         statistics over what is stored, and only over that
  icons.tsx            four inline SVGs, so there is no icon dependency
src/styles.css         tokens first, then components; both themes defined at token level
```

## Two rules this app is built on

**Nothing is decided in the browser.** Every label, confidence, warmth number
and season came back from the API. The one deliberate exception is
`Derivation.tsx`, which re-computes the warmth sum from `/ontology` in order to
show the arithmetic; if it ever disagrees with the number the server sent, it
says so on screen rather than hiding it.

**States are named honestly.** Connecting, backend down, first analysis loading
600MB of weights, later analyses taking three seconds, graph unreachable: each
one has its own wording. A spinner with no explanation is the failure mode this
app is written to avoid.

## Build

```bash
npm run build      # tsc -b && vite build, output in dist/
npm run preview
```

`dist/` is static and can be served by anything. If it is served from a public
HTTPS address while the backend stays on localhost, the browser will block the
calls; put the backend behind a tunnel and point `VITE_API_URL` at it. See
`../FRONTEND_PROMPT.md`.
