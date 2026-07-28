import { useEffect, useState } from "react";
import { ApiError, photoUrl, wardrobeProfile } from "../api";
import type { OutfitValue, Tally, WardrobeProfile } from "../types";

/**
 * The wardrobe read back to its owner: what they mostly wear, the palette they
 * buy in, what the collection is worth, and which weather it cannot yet dress
 * for. Counts and sums over their own clothes, nothing about the model. The gap
 * list is the pointed part: it names the specific thing missing for each season.
 */
/** "a, b and c" — a list a person would read aloud, not one joined by commas. */
function joinWords(parts: string[]): string {
  if (parts.length <= 1) return parts[0] ?? "";
  return `${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}`;
}

function Palette({ rows, swatch }: { rows: Tally[]; swatch?: boolean }) {
  const max = Math.max(1, ...rows.map((r) => r.n));
  if (rows.length === 0) return <p className="reading-empty">nothing yet</p>;
  return (
    <div className="palette">
      {rows.map((r) => (
        <div className="palette-row" key={r.name}>
          <span className="palette-label">
            {swatch && <span className="swatch" data-color={r.name} />}
            {r.name}
          </span>
          <span className="palette-track">
            <span className="palette-fill" style={{ width: `${(r.n / max) * 100}%` }} />
          </span>
          <span className="palette-n">{r.n}</span>
        </div>
      ))}
    </div>
  );
}

function OutfitLine({
  label,
  outfit,
  sym,
}: {
  label: string;
  outfit: OutfitValue | null;
  sym: string;
}) {
  if (!outfit) return null;
  return (
    <div className="value-outfit">
      <div className="value-outfit-head">
        <span className="vo-label">{label}</span>
        <span className="vo-total">
          {sym}
          {outfit.total.toFixed(2)}
        </span>
      </div>
      <div className="value-outfit-pieces">
        {outfit.pieces.map((p) => (
          <figure key={p.id} title={`${p.category ?? ""} · ${sym}${p.price?.toFixed(2)}`}>
            {p.photo_url ? (
              <img src={photoUrl(p.photo_url)} alt={p.category ?? "garment"} loading="lazy" />
            ) : (
              <span className="no-photo">·</span>
            )}
          </figure>
        ))}
      </div>
    </div>
  );
}

export default function Profile({
  enabled,
  refreshKey,
}: {
  enabled: boolean;
  refreshKey: number;
}) {
  const [profile, setProfile] = useState<WardrobeProfile | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled) return;
    wardrobeProfile()
      .then((p) => {
        setProfile(p);
        setError(null);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : String(e)));
  }, [enabled, refreshKey]);

  if (!enabled) {
    return (
      <p className="banner">
        Your wardrobe profile needs the graph, which is where the wardrobe lives.
      </p>
    );
  }
  if (error) return <p className="banner bad">{error}</p>;
  if (!profile) return <p className="reading-empty">reading your wardrobe</p>;

  if (profile.count === 0) {
    return (
      <p className="banner">
        Nothing saved yet, so there is nothing to profile. Analyse a photo with
        “save” ticked and this fills in.
      </p>
    );
  }

  const sym = profile.currency_symbol;
  const v = profile.value;

  return (
    <div className="profile">
      <div className="profile-summary">
        <div className="ps-tile">
          <span className="ps-k">mostly</span>
          <span className="ps-v">{profile.dominant_style ?? "—"}</span>
          <span className="ps-note">{profile.dominant_color ?? ""}</span>
        </div>
        <div className="ps-tile">
          <span className="ps-k">worth</span>
          <span className="ps-v">
            {sym}
            {v.total_value.toFixed(2)}
          </span>
          <span className="ps-note">
            {v.priced} priced, {v.unpriced} not
          </span>
        </div>
        <div className="ps-tile">
          <span className="ps-k">garments</span>
          <span className="ps-v">{profile.count}</span>
          <span className="ps-note">across the body</span>
        </div>
        {v.most_valuable_item && (
          <div className="ps-tile ps-item">
            {v.most_valuable_item.photo_url && (
              <img src={photoUrl(v.most_valuable_item.photo_url)} alt="most valuable" />
            )}
            <div>
              <span className="ps-k">dearest piece</span>
              <span className="ps-v small">
                {sym}
                {v.most_valuable_item.price?.toFixed(2)}
              </span>
              <span className="ps-note">{v.most_valuable_item.category}</span>
            </div>
          </div>
        )}
      </div>

      <div className="profile-grid">
        <div className="panel">
          <div className="stat-head">
            <h3>Your style</h3>
            <span className="aside">how the collection splits</span>
          </div>
          <Palette rows={profile.styles} />
        </div>

        <div className="panel">
          <div className="stat-head">
            <h3>Your palette</h3>
            <span className="aside">colours you own</span>
          </div>
          <Palette rows={profile.colors} swatch />
        </div>

        <div className="panel">
          <div className="stat-head">
            <h3>Materials</h3>
            <span className="aside">what it is made of</span>
          </div>
          <Palette rows={profile.materials} />
        </div>

        <div className="panel">
          <div className="stat-head">
            <h3>Value</h3>
            <span className="aside">priced garments only</span>
          </div>
          {v.priced === 0 ? (
            <p className="reading-empty">
              No prices set yet. Add a price on a garment in the wardrobe and the
              most and least valuable outfits appear here.
            </p>
          ) : (
            <div className="values">
              <OutfitLine label="most valuable outfit" outfit={v.most_valuable_outfit} sym={sym} />
              <OutfitLine label="least valuable outfit" outfit={v.least_valuable_outfit} sym={sym} />
            </div>
          )}
        </div>
      </div>

      <div className="panel gaps-panel">
        <div className="stat-head">
          <h3>Ready for the weather?</h3>
          <span className="aside">what is missing, season by season</span>
        </div>
        <div className="gaps">
          {profile.gaps.map((gap) => (
            <div className="gap" key={gap.season} data-ready={gap.ready}>
              <div className="gap-head">
                <span className="gap-season">{gap.season}</span>
                <span className="gap-range">{gap.temp_range}</span>
                <span className={`gap-badge ${gap.ready ? "ok" : "warn"}`}>
                  {gap.ready ? "ready" : `${gap.fitting} pieces`}
                </span>
              </div>
              {gap.missing.length > 0 ? (
                <ul className="gap-missing">
                  {gap.missing.map((m) => (
                    <li key={m}>{m}</li>
                  ))}
                </ul>
              ) : (
                <p className="gap-ok">
                  covered, head to foot
                  {gap.season !== "hot" && gap.season !== "warm"
                    ? ", with an outer layer"
                    : ""}
                </p>
              )}
              {/* what you will regret not having, kept apart from what you
                  cannot leave the house without */}
              {gap.advisable?.length > 0 && (
                <p className="gap-advisable">
                  In this weather you would also want something for{" "}
                  {joinWords(
                    gap.advisable.map((a) => `the ${a.replace(/^nothing for the /, "")}`)
                  )}
                  .
                </p>
              )}
            </div>
          ))}
        </div>
        <p className="prose">
          A season is “ready” when the wardrobe has something warm enough for the
          upper body, the lower body, the feet, and, for the cold seasons, a real
          outer layer. Below that line sit the things you would merely regret
          being without — a hat in January is not the same kind of missing as
          trousers. Missing pieces are the honest shopping list.
        </p>
      </div>
    </div>
  );
}
