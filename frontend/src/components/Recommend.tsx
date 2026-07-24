import { useCallback, useEffect, useState } from "react";
import { ApiError, photoUrl, recommend } from "../api";
import type { Ontology, Recommendation } from "../types";

/**
 * What to wear today, built from the wardrobe and the person's taste.
 *
 * The season buttons set the target temperature; the backend fills the outfit
 * slot by slot from what is actually owned, preferring liked styles and colours.
 * It is a heuristic and says so, and when the wardrobe cannot cover the weather
 * it lists what is missing rather than inventing a garment to fill the gap.
 */
export default function Recommend({
  enabled,
  ontology,
  refreshKey,
}: {
  enabled: boolean;
  ontology: Ontology | null;
  refreshKey: number;
}) {
  const [season, setSeason] = useState<string | null>(null);
  const [rec, setRec] = useState<Recommendation | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (which: string | null) => {
      setBusy(true);
      setError(null);
      try {
        setRec(await recommend(which));
      } catch (e) {
        setError(e instanceof ApiError ? e.message : String(e));
        setRec(null);
      } finally {
        setBusy(false);
      }
    },
    []
  );

  useEffect(() => {
    if (enabled) void load(season);
  }, [enabled, season, refreshKey, load]);

  if (!enabled) {
    return (
      <p className="banner">
        The recommender reads the wardrobe, which needs the graph. Analysis works
        without it; dressing you does not.
      </p>
    );
  }

  const seasons = ontology?.seasons ?? [];
  const sym = rec?.currency_symbol ?? ontology?.currency_symbol ?? "";

  return (
    <div className="recommend">
      <div className="season-picker">
        <button
          className="chip"
          aria-pressed={season === null}
          onClick={() => setSeason(null)}
        >
          my usual weather
          {rec?.preferences?.home_season && season === null && (
            <small>{rec.preferences.home_season}</small>
          )}
        </button>
        {seasons.map((s) => (
          <button
            key={s.name}
            className="chip"
            aria-pressed={season === s.name}
            onClick={() => setSeason(s.name)}
          >
            {s.name}
            <small>{s.temp_range}</small>
          </button>
        ))}
      </div>

      {error && <p className="banner bad">{error}</p>}
      {busy && <p className="reading-empty">composing an outfit</p>}

      {rec && !busy && (
        <div className="panel outfit-panel">
          <div className="outfit-head">
            <div>
              <p className="outfit-for">
                for <b>{rec.season}</b> weather, {rec.temp_range}
              </p>
              <p className="outfit-sub">
                aiming for warmth {rec.target_warmth}/11
                {rec.outfit_warmth != null && ` · this outfit reaches ${rec.outfit_warmth}`}
                {rec.preferences.runs_cold && " · adjusted, you feel the cold"}
                {rec.preferences.runs_warm && " · adjusted, you run warm"}
              </p>
            </div>
            <span className={`outfit-status ${rec.complete ? "ok" : "warn"}`}>
              {rec.complete ? "complete" : "incomplete"}
            </span>
          </div>

          {rec.outfit.length > 0 ? (
            <div className="outfit">
              {rec.outfit.map((piece) => (
                <figure className="outfit-piece" key={piece.id}>
                  {piece.photo_url ? (
                    <img src={photoUrl(piece.photo_url)} alt={piece.category ?? "garment"} loading="lazy" />
                  ) : (
                    <span className="no-photo">no picture</span>
                  )}
                  <figcaption>
                    <span className="op-name">{piece.category}</span>
                    <span className="op-sub">
                      {[piece.color, piece.material].filter(Boolean).join(" ")}
                    </span>
                    {piece.price != null && (
                      <span className="op-price">
                        {sym}
                        {piece.price.toFixed(2)}
                      </span>
                    )}
                  </figcaption>
                </figure>
              ))}
            </div>
          ) : (
            <p className="reading-empty">
              Nothing in the wardrobe fits this weather yet. Save some garments and
              try again.
            </p>
          )}

          {rec.reasons.length > 0 && (
            <p className="outfit-reasons">{rec.reasons.join(", ")}.</p>
          )}

          {rec.missing.length > 0 && (
            <div className="outfit-missing">
              <span className="missing-tag">missing</span>
              <ul>
                {rec.missing.map((m) => (
                  <li key={m}>{m}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
