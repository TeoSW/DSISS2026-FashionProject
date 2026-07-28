import type { Region } from "../types";
import { REGION_TITLES } from "../types";

/**
 * The way into the wardrobe: click a part of the body, get what is worn there.
 *
 * It used to carry three zones, because the ontology carried three regions and
 * a cloth segmenter that had never seen a shoe. There are nine now — head,
 * neck, upper, hands, waist, lower, feet, the dress form for one-piece
 * garments, and a bag hanging beside the stand for what is carried rather than
 * worn. A figure with nowhere to put a hat is a figure that quietly teaches you
 * the system cannot hold one.
 *
 * Each zone is a real button with a label and a count, so the picker works from
 * the keyboard and reads correctly to a screen reader. What it triggers is a
 * Cypher traversal through (Category)-[:WORN_ON]->(Region), not a filter
 * applied to a list already in the browser.
 */

/**
 * Declared at module level, not inside Mannequin. A component defined in
 * another component's body is a new component type on every render, so React
 * throws the zone away and builds a fresh one each time the selection changes,
 * and whatever the keyboard was focused on disappears mid-interaction.
 */
function Zone({
  region,
  d,
  count,
  selected,
  onPick,
}: {
  region: Region;
  d: string;
  count: number;
  selected: boolean;
  onPick: (region: Region | null) => void;
}) {
  const toggle = () => onPick(selected ? null : region);
  return (
    <path
      d={d}
      className="zone"
      data-selected={selected}
      data-empty={count === 0}
      role="button"
      tabIndex={0}
      aria-label={`${REGION_TITLES[region]}, ${count} pieces`}
      aria-pressed={selected}
      onClick={toggle}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          toggle();
        }
      }}
    />
  );
}

// The figure, as paths. Kept as data rather than as markup so the nine zones
// read as one table instead of as ninety lines of JSX.
const SHAPES: { region: Region; d: string }[] = [
  // the head: a rounded box rather than the old circle, because a circle with a
  // hat on it is a circle
  { region: "head", d: "M48 8 h28 a4 4 0 0 1 4 4 v22 a18 18 0 0 1 -36 0 v-22 a4 4 0 0 1 4 -4 Z" },
  { region: "neck", d: "M55 36 h14 v10 h-14 Z" },
  { region: "upper", d: "M62 47 L92 57 L98 106 L88 110 L84 84 L84 138 L40 138 L40 84 L36 110 L26 106 L32 57 Z" },
  // the waist: a band where a belt sits, between the two halves
  { region: "waist", d: "M40 141 h44 v13 h-44 Z" },
  { region: "lower", d: "M40 157 h44 l-3 44 l-5 58 h-12 l-3 -49 l-3 49 h-12 l-5 -58 Z" },
  // the feet: two shoes, toes outward
  { region: "feet", d: "M42 262 h14 v9 a3 3 0 0 1 -3 3 h-17 a2 2 0 0 1 -1 -4 l7 -4 Z M68 262 h14 l0 4 l7 4 a2 2 0 0 1 -1 4 h-17 a3 3 0 0 1 -3 -3 Z" },
  // the hands: where they hang, one either side
  { region: "hands", d: "M18 112 a7 8 0 1 0 0.1 0 Z M100 112 a7 8 0 1 0 0.1 0 Z" },
  // the dress form beside the figure: one-piece garments hang here
  { region: "full", d: "M167 42 l22 12 l-6 26 l14 122 h-60 l14 -122 l-6 -26 Z" },
  // and a bag on the floor for what is carried rather than worn
  { region: "carried", d: "M136 232 h30 v34 h-30 Z M143 232 v-7 a8 8 0 0 1 16 0 v7" },
];

export default function Mannequin({
  counts,
  active,
  onPick,
}: {
  counts: Partial<Record<Region, number>>;
  active: Region | null;
  onPick: (region: Region | null) => void;
}) {
  const n = (r: Region) => counts[r] ?? 0;
  // every region worth a chip: the nine, plus unplaced when anything landed
  // there. A region with nothing in it still gets a chip, because "you own no
  // hats" is an answer and an empty list is not.
  const legend: Region[] = [
    "upper", "lower", "full", "feet", "head", "neck", "hands", "waist", "carried",
  ];

  return (
    <div className="figure">
      <svg viewBox="0 0 210 300" className="mannequin" aria-label="pick a part of the body">
        {/* the stand, so the figure reads as a tailor's dummy and not a person */}
        <g className="stand">
          <path d="M62 274v10" />
          <path d="M44 288h36" />
          <ellipse cx="62" cy="288" rx="20" ry="4" />
        </g>
        <g className="dress-form">
          <path d="M150 30h34" />
          <path d="M167 30v10" />
        </g>

        {SHAPES.map(({ region, d }) => (
          <Zone
            key={region}
            region={region}
            d={d}
            count={n(region)}
            selected={active === region}
            onPick={onPick}
          />
        ))}

        {/* Only the three large zones carry a printed count. A numeral inside a
            nine-pixel glove is not a reading, and the legend below already says
            every number exactly once. */}
        <text className="zone-n" x="62" y="100" textAnchor="middle">{n("upper")}</text>
        <text className="zone-n" x="62" y="196" textAnchor="middle">{n("lower")}</text>
        <text className="zone-n" x="167" y="140" textAnchor="middle">{n("full")}</text>
      </svg>

      <div className="figure-legend">
        {legend.map((r) => (
          <button
            key={r}
            className="chip"
            aria-pressed={active === r}
            onClick={() => onPick(active === r ? null : r)}
          >
            {REGION_TITLES[r]}
            <small>{n(r)}</small>
          </button>
        ))}
        {n("unplaced") > 0 && (
          <button
            className="chip"
            aria-pressed={active === "unplaced"}
            onClick={() => onPick(active === "unplaced" ? null : "unplaced")}
          >
            unplaced
            <small>{n("unplaced")}</small>
          </button>
        )}
        {active && (
          <button className="btn link" onClick={() => onPick(null)}>
            show everything
          </button>
        )}
      </div>
    </div>
  );
}
