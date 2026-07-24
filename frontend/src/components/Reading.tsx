import type { Analysis } from "../types";
import { GROUPS } from "../types";

const LOW = 0.4; // below this the model is genuinely unsure and says so

function Row({ group, label, confidence }: { group: string; label: string; confidence: number }) {
  const low = confidence < LOW;
  return (
    <div className="row">
      <span className="group">{group}</span>
      <span className="label" title={label}>
        {label}
      </span>
      <span className="track" aria-hidden="true">
        <span
          className="fill"
          data-low={low}
          style={{ width: `${Math.max(2, Math.round(confidence * 100))}%` }}
        />
      </span>
      <span className="num">{(confidence * 100).toFixed(1)}%</span>
      {low && <span className="low">low confidence</span>}
    </div>
  );
}

/**
 * The answer. The cutout sits beside the original so the background removal is
 * visible rather than claimed, and every confidence is printed at one decimal
 * place, including the bad ones: a number that is hidden when it is low is not
 * a measurement.
 */
export default function Reading({
  analysis,
  original,
  children,
}: {
  analysis: Analysis;
  original: string | null;
  children?: React.ReactNode;
}) {
  const ordered = GROUPS.filter((g) => analysis.tags[g]);

  return (
    <div className="panel">
      <p className="headline">{analysis.summary || "no label"}</p>
      <p className="subhead">
        {analysis.saved && analysis.id
          ? `stored as ${analysis.id}`
          : "not stored"}{" "}
        · analysis {analysis.analysis_id}
      </p>

      {(original || analysis.cutout) && (
        <div className="pair">
          {original && (
            <figure>
              <img src={original} alt="the photo as uploaded" />
              <figcaption>as uploaded</figcaption>
            </figure>
          )}
          {analysis.cutout && (
            <figure>
              <img src={analysis.cutout} alt="the same photo with the background removed" />
              <figcaption>background removed</figcaption>
            </figure>
          )}
        </div>
      )}

      <div className="rows">
        {ordered.map((g) => (
          <Row
            key={g}
            group={g}
            label={analysis.tags[g].label}
            confidence={analysis.tags[g].confidence}
          />
        ))}
      </div>

      <div className="meter">
        <span className="value">
          {analysis.warmth}
          <span>/11</span>
        </span>
        <span className="ticks" aria-hidden="true">
          {Array.from({ length: 11 }, (_, i) => (
            <span key={i} className="tick" data-on={i < analysis.warmth} />
          ))}
        </span>
        <span className="group" style={{ fontFamily: "var(--mono)" }}>
          {analysis.layer} layer
        </span>
      </div>

      <div className="chips">
        {analysis.seasons.length === 0 && (
          <span className="chip">no season window matched</span>
        )}
        {analysis.seasons.map((s) => (
          <span className="chip" key={s.name}>
            {s.name}
            <small>{s.temp_range}</small>
          </span>
        ))}
      </div>

      {children}
    </div>
  );
}
