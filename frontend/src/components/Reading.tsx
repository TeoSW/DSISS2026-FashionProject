import { photoUrl } from "../api";
import type { GarmentResult, Method } from "../types";
import { GROUPS, REGION_TITLES } from "../types";

const LOW = 0.4; // below this the model is genuinely unsure and says so

// How this piece came to be here. Segmentation cut it out of the photo; a band
// is a strip of the photo where the region had to be; a probe is a yes/no
// question about the whole picture and is the weakest of the three. Saying
// which is the difference between a determination and an assertion.
const PROVENANCE: Record<Method, string> = {
  segment: "cut from the photograph",
  band: "found in a close crop",
  probe: "inferred from the whole photograph",
  reported: "reported by you",
};

/**
 * One typed line of the determination label.
 *
 * Below 0.40 the value is prefixed `cf.`, which is the botanist's own mark for
 * "compare with — I am not certain of this". It is a more honest word than a
 * warning badge, it is the vocabulary of the world this interface is set in,
 * and the measured number stays printed beside it either way.
 */
function Row({ group, label, confidence }: { group: string; label: string; confidence: number }) {
  const low = confidence < LOW;
  return (
    <div className="row">
      <span className="group">{group}</span>
      <span className="label" title={label}>
        {low && <i className="cf">cf.</i>}
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
    </div>
  );
}

/**
 * One garment's reading, laid out as a herbarium sheet: the cutout mounted on
 * the left under its straps, the determination label pasted into the lower
 * right with the accession stamp on its head rule, and the derived warmth read
 * off a printed scale below.
 *
 * Its own cutout is the mounted specimen, so when a photo held several garments
 * each sheet shows the piece it is actually about rather than the whole picture
 * repeated. Every confidence is printed at one decimal, the low ones included:
 * a number hidden when it is small is not a measurement.
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
  const filed = !!(garment.saved && garment.id);

  return (
    <div className="panel reading-card">
      <div className="reading-top">
        {src && (
          <figure className="reading-cut">
            <img src={src} alt={garment.summary || "garment"} />
          </figure>
        )}

        <div className="det-label">
          <div className="det-head">
            <span>determination</span>
            <span className="accession" data-filed={filed}>
              {filed ? garment.id : "not accessioned"}
            </span>
          </div>

          <p className="headline">{garment.summary || "no label"}</p>
          <p className="subhead">
            {multi && (
              <span className="region-tag">
                {REGION_TITLES[garment.region] ?? garment.region}
              </span>
            )}
            {PROVENANCE[garment.method] ?? "det. by machine"}
            {garment.presence != null && garment.method !== "segment" && (
              <span className="presence"> · {(garment.presence * 100).toFixed(0)}% there</span>
            )}
          </p>

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

      {/* A ring has a warmth score because the arithmetic is the same
          arithmetic for everything, and it means nothing. Rather than print a
          scale that says a bracelet is hot-weather equipment, the piece says
          why it has no reading. */}
      {garment.seasonal ? (
        <>
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
            <span className="layer-note">{garment.layer} layer</span>
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
        </>
      ) : (
        <p className="not-weather">
          A {garment.tags.category?.label ?? "piece"} is not weather. It is
          stored, counted and correctable like everything else, but it claims no
          season — otherwise a wardrobe reports itself ready for winter on the
          strength of a bracelet.
        </p>
      )}

      {children}
    </div>
  );
}
