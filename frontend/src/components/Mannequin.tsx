import type { Region } from "../types";

/**
 * The way into the wardrobe: click a part of the body, get what is worn there.
 *
 * Two zones on the figure, upper and lower, plus a dress form standing beside
 * it for the full-length rail. The alternative was a third zone overlapping the
 * first two, which is how you build a target nobody can hit on purpose.
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
  label,
  count,
  selected,
  onPick,
}: {
  region: Region;
  d: string;
  label: string;
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
      aria-label={`${label}, ${count} garments`}
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

  return (
    <div className="figure">
      <svg viewBox="0 0 210 300" className="mannequin" aria-label="pick a part of the body">
        {/* the stand, so the figure reads as a tailor's dummy and not a person */}
        <g className="stand">
          <path d="M62 268v16" />
          <path d="M44 288h36" />
          <ellipse cx="62" cy="288" rx="20" ry="4" />
        </g>

        <circle className="head" cx="62" cy="24" r="14" />
        <path className="neck" d="M56 37h12v7" />

        <Zone
          region="upper"
          label="upper body"
          count={n("upper")}
          selected={active === "upper"}
          onPick={onPick}
          d="M62 44 L92 54 L98 104 L88 108 L84 82 L84 150 L40 150 L40 82 L36 108 L26 104 L32 54 Z"
        />
        <Zone
          region="lower"
          label="lower body"
          count={n("lower")}
          selected={active === "lower"}
          onPick={onPick}
          d="M40 154 h44 l-3 46 l-5 62 h-12 l-3 -52 l-3 52 h-12 l-5 -62 Z"
        />

        {/* the dress form: full-length garments hang here */}
        <g className="dress-form">
          <path d="M150 30h34" />
          <path d="M167 30v10" />
        </g>
        <Zone
          region="full"
          label="full length"
          count={n("full")}
          selected={active === "full"}
          onPick={onPick}
          d="M167 42 l22 12 l-6 26 l14 122 h-60 l14 -122 l-6 -26 Z"
        />

        <text className="zone-n" x="62" y="102" textAnchor="middle">
          {n("upper")}
        </text>
        <text className="zone-n" x="62" y="196" textAnchor="middle">
          {n("lower")}
        </text>
        <text className="zone-n" x="167" y="140" textAnchor="middle">
          {n("full")}
        </text>
      </svg>

      <div className="figure-legend">
        {(["upper", "lower", "full"] as Region[]).map((r) => (
          <button
            key={r}
            className="chip"
            aria-pressed={active === r}
            onClick={() => onPick(active === r ? null : r)}
          >
            {r === "full" ? "full length" : `${r} body`}
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
