import { useEffect, useState } from "react";
import { ApiError, preferences, putPreferences } from "../api";
import type { Ontology, Preferences as Prefs } from "../types";

/**
 * The person's taste, as a few toggles. These only tilt the recommender: a
 * disliked colour is shown less, never hidden, because it is their own wardrobe
 * and they are allowed to wear the thing they said they dislike. Everything
 * validates against the ontology server side, so a stray value cannot get in.
 */
export default function Preferences({
  enabled,
  ontology,
  onSaved,
}: {
  enabled: boolean;
  ontology: Ontology | null;
  onSaved: () => void;
}) {
  const [prefs, setPrefs] = useState<Prefs | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!enabled) return;
    preferences().then(setPrefs).catch(() => undefined);
  }, [enabled]);

  if (!enabled || !prefs) return null;

  const styles = ontology?.attributes.style ?? [];
  const colors = ontology?.attributes.color ?? [];
  const seasons = ontology?.seasons ?? [];

  function toggle(list: string[], value: string): string[] {
    return list.includes(value) ? list.filter((x) => x !== value) : [...list, value];
  }

  async function commit(next: Prefs) {
    setPrefs(next);
    setBusy(true);
    setError(null);
    try {
      const stored = await putPreferences(next);
      setPrefs(stored);
      setSaved(true);
      setTimeout(() => setSaved(false), 1500);
      onSaved();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="panel prefs">
      <div className="prefs-row">
        <span className="prefs-k">styles you reach for</span>
        <div className="prefs-chips">
          {styles.map((s) => (
            <button
              key={s}
              className="chip"
              aria-pressed={prefs.preferred_styles.includes(s)}
              onClick={() => commit({ ...prefs, preferred_styles: toggle(prefs.preferred_styles, s) })}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      <div className="prefs-row">
        <span className="prefs-k">colours you like</span>
        <div className="prefs-chips">
          {colors.map((c) => (
            <button
              key={c}
              className="chip swatch-chip"
              aria-pressed={prefs.preferred_colors.includes(c)}
              onClick={() => commit({ ...prefs, preferred_colors: toggle(prefs.preferred_colors, c) })}
            >
              <span className="swatch" data-color={c} />
              {c}
            </button>
          ))}
        </div>
      </div>

      <div className="prefs-row">
        <span className="prefs-k">colours you avoid</span>
        <div className="prefs-chips">
          {colors.map((c) => (
            <button
              key={c}
              className="chip swatch-chip danger-chip"
              aria-pressed={prefs.disliked_colors.includes(c)}
              onClick={() => commit({ ...prefs, disliked_colors: toggle(prefs.disliked_colors, c) })}
            >
              <span className="swatch" data-color={c} />
              {c}
            </button>
          ))}
        </div>
      </div>

      <div className="prefs-row">
        <span className="prefs-k">your usual weather</span>
        <div className="prefs-chips">
          {seasons.map((s) => (
            <button
              key={s.name}
              className="chip"
              aria-pressed={prefs.home_season === s.name}
              onClick={() => commit({ ...prefs, home_season: s.name })}
            >
              {s.name}
              <small>{s.temp_range}</small>
            </button>
          ))}
        </div>
      </div>

      <div className="prefs-row">
        <span className="prefs-k">how you feel it</span>
        <div className="prefs-chips">
          <button
            className="chip"
            aria-pressed={prefs.runs_cold}
            onClick={() => commit({ ...prefs, runs_cold: !prefs.runs_cold, runs_warm: false })}
          >
            I feel the cold
          </button>
          <button
            className="chip"
            aria-pressed={prefs.runs_warm}
            onClick={() => commit({ ...prefs, runs_warm: !prefs.runs_warm, runs_cold: false })}
          >
            I run warm
          </button>
        </div>
      </div>

      <p className="prefs-foot">
        {error ? (
          <span className="bad-text">{error}</span>
        ) : saved ? (
          <span className="good-text">saved</span>
        ) : busy ? (
          "saving…"
        ) : (
          "hints for the recommender, never a filter on your own clothes"
        )}
      </p>
    </div>
  );
}
