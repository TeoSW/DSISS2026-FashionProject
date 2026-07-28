---
name: Fitting Room
description: A herbarium sheet for the clothes you own — every reading is a dated determination, and no determination is ever erased.
colors:
  rag-paper: "#efe9dd"
  sheet: "#f7f3e9"
  mounting-well: "#e5dccb"
  iron-gall: "#201d18"
  iron-gall-2: "#55503f"
  iron-gall-3: "#6a6250"
  stamp-blue: "#2c4a78"
  stamp-blue-wash: "rgba(44, 74, 120, 0.10)"
  annotation-ochre: "#8a5a12"
  oxblood: "#8c2f24"
  verified-green: "#3a6138"
  board: "#14130f"
  board-sheet: "#1d1b16"
  board-well: "#100f0c"
  chalk: "#ece5d5"
  chalk-2: "#b1a993"
  chalk-3: "#948c78"
  stamp-blue-light: "#8fadde"
typography:
  display:
    fontFamily: "Constantia, \"Palatino Linotype\", Palatino, \"Iowan Old Style\", \"Book Antiqua\", Georgia, serif"
    fontSize: "28px"
    fontWeight: 400
    lineHeight: 1.18
    letterSpacing: "-0.012em"
  headline:
    fontFamily: "Constantia, \"Palatino Linotype\", Palatino, \"Iowan Old Style\", \"Book Antiqua\", Georgia, serif"
    fontSize: "19px"
    fontWeight: 400
    lineHeight: 1.25
    letterSpacing: "0.01em"
  title:
    fontFamily: "Constantia, \"Palatino Linotype\", Palatino, \"Iowan Old Style\", \"Book Antiqua\", Georgia, serif"
    fontSize: "15.5px"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "normal"
  body:
    fontFamily: "Constantia, \"Palatino Linotype\", Palatino, \"Iowan Old Style\", \"Book Antiqua\", Georgia, serif"
    fontSize: "15.5px"
    fontWeight: 400
    lineHeight: 1.58
    letterSpacing: "normal"
  label:
    fontFamily: "ui-monospace, \"Cascadia Mono\", Consolas, \"SF Mono\", \"Roboto Mono\", monospace"
    fontSize: "10.5px"
    fontWeight: 400
    lineHeight: 1.4
    letterSpacing: "0.14em"
    fontFeature: "tnum"
  field:
    fontFamily: "ui-monospace, \"Cascadia Mono\", Consolas, \"SF Mono\", \"Roboto Mono\", monospace"
    fontSize: "12.5px"
    fontWeight: 400
    lineHeight: 1.45
    letterSpacing: "0.01em"
    fontFeature: "tnum"
rounded:
  none: "0px"
  hair: "1px"
  well: "2px"
spacing:
  hair: "4px"
  tight: "8px"
  field: "12px"
  block: "20px"
  sheet: "30px"
  section: "44px"
components:
  button-primary:
    backgroundColor: "{colors.iron-gall}"
    textColor: "{colors.sheet}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "11px 20px"
  button-primary-hover:
    backgroundColor: "{colors.stamp-blue}"
    textColor: "{colors.sheet}"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.iron-gall}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "11px 20px"
  button-ghost-hover:
    backgroundColor: "{colors.stamp-blue-wash}"
    textColor: "{colors.stamp-blue}"
  sheet:
    backgroundColor: "{colors.sheet}"
    rounded: "{rounded.none}"
    padding: "20px"
  det-label:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.iron-gall}"
    typography: "{typography.field}"
    rounded: "{rounded.none}"
    padding: "12px 14px"
  accession-stamp:
    backgroundColor: "transparent"
    textColor: "{colors.stamp-blue}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "3px 8px"
  tab:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.iron-gall}"
    typography: "{typography.field}"
    rounded: "{rounded.none}"
    padding: "5px 11px"
  tab-selected:
    backgroundColor: "{colors.stamp-blue-wash}"
    textColor: "{colors.stamp-blue}"
  field-input:
    backgroundColor: "transparent"
    textColor: "{colors.iron-gall}"
    typography: "{typography.field}"
    rounded: "{rounded.none}"
    padding: "8px 2px"
---

# Design System: Fitting Room

## Overview

**Creative North Star: "The Herbarium Sheet"**

A botanist does not photograph a plant and call it identified. They mount it on rag
paper, type a determination label, sign it, date it, and paste it in the lower right
corner. When someone later disagrees, they do not erase that label — they paste an
annotation slip beneath it. Both readings stay on the sheet forever, and the sheet is
the record.

Fitting Room reads a photograph of a garment you own and returns a determination: a
category, a material, a sleeve, a colour, a style, each with a confidence, and a warmth
derived by walking a graph rather than predicted. When you correct it, the correction is
written to Neo4j beside the original — not over it. That is a herbarium sheet, and so the
interface is one. The garment cutout is the mounted specimen. The reading is the typed
determination label. Your correction is the annotation slip. The twelve-character garment
id is the accession number, stamped. Warmth 1–11 and the season windows are an ecological
range chart. Uncertainty below 40% is not a red badge, it is `cf.` — the botanist's own
word for *compare with; I am not sure*.

The world is warm rag paper under lamp light, iron-gall ink, and one ink of institutional
stamp blue. In the dark it is not "the same page inverted" — it is black conservation
mount board, which is a real thing specimens are mounted on, with cream ink. Corners are
square, because a pasted paper label has square corners. Rules are hairlines, because a
printed form has hairlines. Two anti-references, both confirmed and both refused: the
glossy pastel masonry grid of fashion-app convention, and its predictable opposite, the
near-black dashboard with a neon accent.

**Key Characteristics:**
- Paper, not glass: warm grounds, hairline rules, zero corner radius, flecked texture
- A serif for everything that is read; a typewriter face for everything that is *recorded*
- One stamp blue for emphasis; ochre reserved solely for `cf.` uncertainty
- Pasted things sit a half-degree off true — labels, stamps, slips, never the layout
- Nothing is erased: a superseded determination stays visible, struck through, beneath its revision

## Colors

Pigments, not a palette: the colour of aged rag paper, the colour of iron-gall ink as it
browns, and the single blue of a collection stamp.

### Primary
- **Stamp Blue** (`#2c4a78`): the institutional ink. Every accession stamp, every active
  state, every filled measurement bar, every link. In the dark world it lightens to
  **Stamp Blue Light** (`#8fadde`) so it stays ink on board rather than glow. It appears on
  well under a tenth of any screen; its rarity is what makes a stamp read as a stamp.

### Secondary
- **Annotation Ochre** (`#8a5a12`, dark `#d8a95e`): one job and one job only — the `cf.`
  mark and the confidence bar beneath a reading below 40%. Seeing ochre anywhere in this
  interface means exactly one thing: the machine is not sure.

### Tertiary
- **Oxblood** (`#8c2f24`, dark `#e8938a`): destruction and failure. Deleting a garment for
  good, an unreachable backend, an invalid price.
- **Verified Green** (`#3a6138`, dark `#86c088`): the botanist's `!` — a determination a
  person has confirmed. Receipts and "ready" verdicts.

### Neutral
- **Rag Paper** (`#efe9dd`): the ground the sheets lie on. Warm, slightly yellowed, never grey.
- **Sheet** (`#f7f3e9`): the mounting sheet itself, one step lighter than the ground so a
  sheet reads as *on top of* the table rather than cut out of it.
- **Mounting Well** (`#e5dccb`): the recessed area a specimen sits in, and the ground of
  every input field and cabinet interior.
- **Iron Gall** (`#201d18`): body ink. Warm-black, never `#000`.
- **Iron Gall 2** (`#55503f`): the ink of secondary prose and captions.
- **Iron Gall 3** (`#6a6250`): the ink of field names and printed captions. Still ≥4.5:1 on
  paper, sheet and well alike — a caption you have to guess at is not a caption.
- **Conservation Board** (`#14130f` / sheet `#1d1b16` / well `#100f0c`) and **Chalk**
  (`#ece5d5` / `#b1a993` / `#948c78`): the dark world. Warm black board, cream ink.

### Named Rules
**The One Ink Rule.** Stamp blue is the only accent. If an element needs to stand out and
blue is already spoken for on that screen, it earns its emphasis from weight, size, or a
rule — not from a new hue.

**The Ochre Means Unsure Rule.** Annotation ochre never decorates. It marks `cf.` and the
confidence bar of a reading below 0.40, and nothing else, ever.

**The Warm Black Rule.** No pure `#000` and no pure `#fff` anywhere. Paper is yellowed and
ink browns; both worlds carry the same warmth so a screenshot of either reads as paper.

## Typography

**Display / Body Font:** Constantia, with Palatino Linotype, Iowan Old Style, Book Antiqua
and Georgia behind it — a transitional text serif present on Windows and macOS, so the
world holds with no webfont and no network. This is a local-only app; a font that needs a
CDN is a font that fails.

**Label / Field Font:** the system monospace stack (Cascadia Mono, SF Mono, Consolas), with
tabular figures on. It is not a costume for "technical": a determination label is *typed*,
and a column of confidences has to line up as a column.

**Character:** printed and typed, in that order. The serif carries everything a person
reads for meaning; the typewriter carries everything the system recorded — names of fields,
identifiers, confidences, dates, ranges. Nothing is set in a UI sans, because nothing here
is a chrome control pretending to be part of an operating system.

### Hierarchy
- **Display** (Constantia 400, 28px, 1.18, -0.012em): the determination — what the garment
  actually is. One per reading, and the largest thing on the sheet after the specimen.
- **Headline** (Constantia 400, 19px, 1.25): section captions, printed on their rule.
- **Title** (Constantia 600, 15.5px): a garment name on a cabinet card, a panel head.
- **Body** (Constantia 400, 15.5px, 1.58, max 68ch): explanatory prose. Never full-bleed.
- **Label** (mono 400, 10.5px, 0.14em, uppercase): printed field names, stamps, captions,
  the sheet footer. Tabular.
- **Field** (mono 400, 12.5px, tabular): recorded values — confidences, prices, warmth,
  accession numbers, temperature ranges.

### Named Rules
**The Typed-Not-Written Rule.** If a value came out of the system, it is set in the
typewriter face. If a sentence was written for a person to read, it is set in the serif.
There is no third case and no mixing inside a single run of text.

**The Small Caps Ceiling Rule.** Tracked uppercase belongs to printed field names and
stamps — things a form would actually print. It never becomes an eyebrow over a section
heading, and it never sets a sentence.

## Layout

A sheet on a table. The page is a 1180px column of warm ground; content sits on discrete
paper sheets with hairline borders and a real cast shadow, separated by 44px of ground.
Inside a sheet the rhythm is 20px, tightening to 12px between a field name and its value
and 8px within a group.

Section captions are printed *on* their rule: a hairline spans the full column, the caption
sits on it in the serif with the ground colour breaking the rule behind it, and the live
readout ("3 garments found", "not open") sits right-aligned on the same rule in the label
face. The three sections that form a reading sequence — mount, determine, derive — carry a
plate number in the label face at the left end of the rule; the wardrobe, the recommender
and the profile do not, because they are places you go rather than steps you take.

Two columns above 940px (specimen left, determination right), one below. The cabinet splits
at 860px into figure and shelves. On coarse pointers every control grows to a 44px hit area
by padding alone, so the typography never shifts between a mouse and a thumb.

## Elevation & Depth

Paper on paper. Depth comes from three sources and no others: **tone** (well is darker than
ground is darker than sheet), **a hairline** at every paper edge, and **a real cast shadow**
with a downward offset and a soft blur, as a sheet lying on a table actually casts. Nothing
glows, nothing frosts, nothing floats on a zero-offset halo.

### Shadow Vocabulary
- **Sheet lift** (`0 1px 2px rgba(32,29,24,.09), 0 12px 26px -10px rgba(32,29,24,.20)`):
  a mounting sheet or a cabinet card resting on the ground.
- **Pasted lift** (`0 1px 1px rgba(32,29,24,.16), 0 3px 7px -3px rgba(32,29,24,.20)`):
  a determination label, annotation slip, or stamp glued onto a sheet. Tighter and darker
  than sheet lift, because the gap is a millimetre of paste.

### Named Rules
**The Millimetre Rule.** A pasted thing casts a millimetre of shadow, not a centimetre.
If a label looks like it is hovering, its blur is too large.

## Shapes

**Zero radius, everywhere, without exception** — except a single 2px on the specimen
mounting well, which is a cut mat and not a pasted label. A guillotine leaves square
corners; so does this interface.

Borders do the structural work: 1px hairlines at every paper edge, a 1px double rule
(border plus a 3px offset outline) around a determination label the way a printed label
carries a ruled frame, and 1.5px on the accession stamp because a rubber stamp lays down
more ink than a printing plate.

**Pasted things sit off true.** Determination labels, annotation slips and accession stamps
carry a rotation between 0.3° and 1.8°, always applied to the pasted element alone and
never to a container that another element measures against. Layout is square; only paste is
crooked.

**The mounting strap** is the recurring silhouette: two short angled hairlines across the
top corners of anything holding a specimen — the drop zone, a cabinet card, the specimen
figure in a reading. It is how you know a thing is mounted rather than merely displayed.

## Components

### Buttons
- **Shape:** square (0px). No radius on any variant.
- **Primary:** iron-gall ink ground, sheet-coloured text, label face, uppercase, 0.10em
  tracking, 11px/20px padding. It reads as a rubber stamp being pressed.
- **Hover / Focus:** ground shifts to stamp blue in 140ms; focus is a 2px stamp-blue
  outline at 2px offset, square.
- **Ghost:** transparent with a 1px hairline; hover fills with stamp-blue wash.
- **Link:** stamp blue, underlined at 3px offset, in the serif — a printed cross-reference.
- **Disabled:** 45% opacity, no shadow, `not-allowed`.

### Chips
Not pills — **pasted tabs**. Square, 1px hairline, sheet ground, 5px/11px, value in the
field face and its range in the label face beside it. Selected tabs take stamp-blue wash,
a stamp-blue border and stamp-blue text.

### Cards / Containers
- **Corner Style:** square (0px).
- **Background:** sheet on ground; the cabinet interior and every well use mounting-well.
- **Shadow:** sheet lift. Cabinet cards additionally carry the mounting strap at the top.
- **Border:** 1px hairline on all four edges, always.
- **Internal Padding:** 20px on a sheet, 12px on a card body.

### Inputs / Fields
- **Style:** no box. A field is a **ruled line** — transparent ground, no border except a
  1px bottom rule, set in the field face, with its printed name above it in the label face.
  This is what a paper form does, and it removes an entire vocabulary of boxes from the page.
- **Focus:** the bottom rule thickens to 2px and turns stamp blue; the printed name turns
  stamp blue with it.
- **Changed:** a value the person overwrote turns stamp blue and its rule with it.
- **Error:** the rule and the message turn oxblood; the message names the problem.

### Navigation
Two typed tabs on the sheet header rule (Wardrobe / Admin), label face, uppercase. The
active tab carries a 2px stamp-blue underline sitting directly on the header rule — a tab
divider in a card index.

### Signature Components

**The determination label** (`.det-label`). A pasted cream label in the lower right of a
reading, carrying a ruled double frame, the determined name in the display serif, and a
typed field block beneath: each attribute group as a printed field name with its value and
confidence in the field face. Rotated -0.4°. Values below 0.40 confidence are prefixed
`cf.` in annotation ochre.

**The accession stamp** (`.accession`). The garment's twelve-character id, uppercase, in a
1.5px stamp-blue box rotated 1.6°, at 82% opacity so the ink reads as absorbed into the
paper. Present wherever a garment is identified, because an accession number is how a
collection refers to a specimen.

**The annotation slip** (`.slip`). A narrow pasted strip beneath a determination, rotated
0.5°, carrying `rev.` and the date, the superseded value struck through in the ink of
prose, and the new value in stamp blue. It never replaces the label above it.

**The ecological range chart** (`.windows`). The season windows: each row a named range
with its span drawn on a 1–11 scale and a single ink needle at this garment's derived
warmth. The row whose span contains the needle takes stamp blue.

**The printed scale** (`.scale-rule`). The warmth meter drawn as an instrument scale —
eleven ticks, every fifth taller and numbered, the value struck as a heavy ink needle. It
replaces a progress bar with a reading.

## Do's and Don'ts

### Do:
- **Do** set every recorded value — confidence, price, warmth, accession, temperature range —
  in the field face with tabular figures, and every written sentence in the serif.
- **Do** keep the determination label pasted in the lower right of a reading. That corner is
  where it goes on a real sheet and moving it costs the whole metaphor.
- **Do** print a confidence below 0.40 as `cf.` in annotation ochre, and leave the number
  visible at one decimal beside it. A number hidden because it is small is not a measurement.
- **Do** show a superseded determination struck through and still legible beneath its
  revision. Nothing in this app is erased.
- **Do** give paste a rotation between 0.3° and 1.8°, applied to the pasted element only.
- **Do** hold both worlds to warm ink: `#201d18` on paper, `#ece5d5` on board.

### Don't:
- **Don't** round a corner. The only radius in the system is 2px on the specimen well.
- **Don't** introduce a second accent. Stamp blue is the accent; ochre is a signal, not a colour.
- **Don't** rotate a container, a grid, or anything another element is measured against.
  Only pasted leaf elements are crooked.
- **Don't** use the label face for a sentence, or the serif for a value out of the API.
- **Don't** use a zero-offset halo, a glass blur, or a coloured left border to convey depth —
  tone, hairline and cast shadow are the only three.
- **Don't** add a tracked uppercase eyebrow above a section caption. The caption sits on its
  rule and that is the whole system.
- **Don't** remove a surface, a statistic or an identifier to tidy the page. This is an alpha
  and the standing instruction is that nothing is taken out — re-express it in the world instead.
