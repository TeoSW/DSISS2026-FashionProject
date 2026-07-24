import type { Analysis, Ontology } from "../types";

/**
 * Why this garment got that weather.
 *
 * The model never predicts a season. It names a material, a category and a
 * sleeve; each of those carries a warmth weight that lives in config.py and is
 * seeded into Neo4j, they are added, and the sum is matched against the season
 * windows. This panel re-does that arithmetic from /ontology and shows it,
 * which is the one thing a demo of this project has to make visible.
 *
 * Re-deriving it in the browser is duplicated logic, and it is worth it: if
 * this panel ever disagreed with the number the server returned, that
 * disagreement is a bug worth seeing rather than hiding behind a single
 * rendered value.
 */
export default function Derivation({
  analysis,
  ontology,
}: {
  analysis: Analysis;
  ontology: Ontology;
}) {
  const material = analysis.tags.material?.label ?? "";
  const category = analysis.tags.category?.label ?? "";
  const sleeve = analysis.tags.sleeve?.label ?? "";

  const mw = ontology.material_warmth[material] ?? 2;
  const cat = ontology.category_warmth[category] ?? { warmth: 2, layer: "base" };
  // trousers have no sleeves: whatever the model answered there is noise, and
  // weather.py drops it for anything worn on the bottom half
  const bottom = cat.layer === "bottom";
  const sw = bottom ? 0 : ontology.sleeve_modifier[sleeve] ?? 0;
  const total = Math.max(1, Math.min(11, mw + cat.warmth + sw));

  const hit = new Set(analysis.seasons.map((s) => s.name));
  const pct = (n: number) => ((n - 1) / 10) * 100;

  return (
    <div className="panel derivation">
      <div className="sum">
        <span className="term">
          <span className="k">{material || "material"}</span>
          <span className="v">{mw}</span>
        </span>
        <span className="op">+</span>
        <span className="term">
          <span className="k">{category || "category"}</span>
          <span className="v">{cat.warmth}</span>
        </span>
        <span className="op">+</span>
        <span className="term">
          <span className="k">{bottom ? "sleeves n/a" : sleeve || "sleeve"}</span>
          <span className="v">
            {sw > 0 ? "+" : ""}
            {sw}
          </span>
        </span>
        <span className="op">=</span>
        <span className="term total">
          <span className="k">warmth</span>
          <span className="v">{total} / 11</span>
        </span>
      </div>

      {total !== analysis.warmth && (
        <p className="banner warn">
          This panel computes {total} from /ontology while the server returned{" "}
          {analysis.warmth}. The two use the same table, so a difference means one
          of them is out of date.
        </p>
      )}

      <div className="windows">
        {ontology.seasons.map((s) => {
          const min = s.warmth_min ?? 1;
          const max = s.warmth_max ?? 11;
          return (
            <div className="window" key={s.name} data-hit={hit.has(s.name)}>
              <span className="name">{s.name}</span>
              <span className="scale">
                <span
                  className="span"
                  style={{ left: `${pct(min)}%`, width: `${pct(max) - pct(min)}%` }}
                />
                <span className="needle" style={{ left: `calc(${pct(total)}% - 1px)` }} />
              </span>
              <span className="range">{s.temp_range}</span>
            </div>
          );
        })}
      </div>

      <p className="prose">
        {bottom
          ? `${category} is worn on the lower body, so the sleeve label is ignored. `
          : `${sleeve || "the sleeve length"} adjusts the sum by ${sw}. `}
        The needle sits at {total}, which falls inside{" "}
        {analysis.seasons.length
          ? analysis.seasons.map((s) => s.name).join(" and ")
          : "no window"}
        .{" "}
        {analysis.saved
          ? "Because this garment was saved, the seasons above were read back out of Neo4j in Cypher rather than computed here."
          : "Save a garment and the same answer comes back from a Cypher traversal instead of this arithmetic."}
      </p>
    </div>
  );
}
