import { photoUrl } from "../api";
import type { GarmentResult } from "../types";
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
 * One garment's reading. Its own cutout is the headline image, so when a photo
 * held several garments each card shows the piece it is actually about rather
 * than the whole picture repeated. Every confidence is printed at one decimal,
 * the low ones included: a number hidden when it is small is not a measurement.
 *
 * `cutout` can be a data URI straight from /analyze or, once saved, the stored
 * image served by the API; both work in an <img src>.
 */
export default function Reading({
  garment,
  multi,
  currencySymbol,
  children,
}: {
  garment: GarmentResult;
  multi: boolean;
  currencySymbol: string;
  children?: React.ReactNode;
}) {
  const ordered = GROUPS.filter((g) => garment.tags[g]);
  const src = garment.cutout ?? (garment.id ? photoUrl(`/garments/${garment.id}/image`) : null);

  return (
    <div className="panel reading-card">
      <div className="reading-top">
        {src && (
          <figure className="reading-cut">
            <img src={src} alt={garment.summary || "garment"} />
          </figure>
        )}
        <div className="reading-lead">
          <p className="headline">{garment.summary || "no label"}</p>
          <p className="subhead">
            {multi && <span className="region-tag">{garment.region} body</span>}
            {garment.saved && garment.id ? `stored as ${garment.id}` : "not stored"}
          </p>
          {(garment.brand || garment.price != null) && (
            <p className="brand-price">
              {garment.brand && <span className="brand">{garment.brand}</span>}
              {garment.price != null && (
                <span className="price">
                  {currencySymbol}
                  {garment.price.toFixed(2)}
                  {garment.price_estimate && (
                    <span className="est" title={garment.price_estimate.basis}>
                      estimated
                    </span>
                  )}
                </span>
              )}
            </p>
          )}
        </div>
      </div>

      <div className="rows">
        {ordered.map((g) => (
          <Row
            key={g}
            group={g}
            label={garment.tags[g].label}
            confidence={garment.tags[g].confidence}
          />
        ))}
      </div>

      <div className="meter">
        <span className="value">
          {garment.warmth}
          <span>/11</span>
        </span>
        <span className="ticks" aria-hidden="true">
          {Array.from({ length: 11 }, (_, i) => (
            <span key={i} className="tick" data-on={i < garment.warmth} />
          ))}
        </span>
        <span className="group" style={{ fontFamily: "var(--mono)" }}>
          {garment.layer} layer
        </span>
      </div>

      <div className="chips">
        {garment.seasons.length === 0 && (
          <span className="chip">no season window matched</span>
        )}
        {garment.seasons.map((s) => (
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
