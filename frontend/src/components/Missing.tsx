import { useMemo, useState } from "react";
import { ApiError, reportMissing } from "../api";
import type { MissedResult, Ontology, Region } from "../types";
import { REGION_TITLES, REGIONS } from "../types";

/**
 * The other half of being wrong.
 *
 * Flag corrects a label the system offered: you called this a shirt, it is a
 * blouse. There is no way to say "there were boots in that photo" as a
 * correction, because there is nothing to correct — the system never mentioned
 * the boots. Until this existed, the only failure it could hear about was the
 * one it had already half-committed to, and a miss looked exactly like a
 * photograph with nothing in it.
 *
 * The form is a region first, then the categories worn there, because that is
 * the shape of the question a person can actually answer: they know where on
 * their body the thing was long before they have scanned a list of fifty-six
 * words looking for it.
 */
export default function Missing({
  analysisId,
  ontology,
  onReported,
}: {
  analysisId: string | null;
  ontology: Ontology | null;
  onReported: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [region, setRegion] = useState<Region>("feet");
  const [category, setCategory] = useState("");
  const [note, setNote] = useState("");
  const [file, setFile] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<MissedResult[]>([]);

  // The API sends the region tables so the browser never keeps a second copy of
  // the ontology that can drift from config.py. Without them, fall back to
  // every category the system knows rather than to nothing.
  const byRegion = ontology?.categories_by_region;
  const choices = useMemo(() => {
    if (byRegion) return byRegion[region] ?? [];
    return ontology?.attributes.category ?? [];
  }, [byRegion, ontology, region]);

  const regions = (ontology?.regions ?? REGIONS) as Region[];
  const title = (r: Region) => ontology?.region_titles?.[r] ?? REGION_TITLES[r];

  async function submit() {
    if (!category) return;
    setBusy(true);
    setError(null);
    try {
      const result = await reportMissing({
        analysis_id: analysisId,
        category,
        note: note.trim(),
        file,
      });
      setDone((d) => [...d, result]);
      setCategory("");
      setNote("");
      onReported();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="missing">
      {done.map((d) => (
        <div className="receipt addendum" key={d.id}>
          <span className="slip-head">
            <b>addendum</b>
            <span className="slip-id">{d.id}</span>
          </span>
          <span className="slip-rev">
            <span className="group">not seen</span>
            <em>{d.category}</em>
            <span>on the {title(d.region)}</span>
          </span>
          <span>
            {d.filed
              ? "added to the wardrobe, marked as your answer rather than the model's — with no picture, because nobody drew a box around it"
              : "recorded as a miss; not added to the wardrobe"}
          </span>
          <span>
            {d.graph_updated
              ? "written to neo4j, where it counts against what this system is blind to"
              : "neo4j unreachable, kept on disk only"}
          </span>
        </div>
      ))}

      {!open ? (
        <button className="btn ghost small missing-open" onClick={() => setOpen(true)}>
          something is missing
        </button>
      ) : (
        <div className="fix">
          <p className="hint">
            Name a piece that was in the photograph and never appeared above.
            This is not a correction — nothing was labelled wrongly, something
            was not seen at all, and the two are different failures with
            different fixes. Where it was on the body is the useful part: a pile
            of misses in one region means nothing is looking there.
          </p>

          <div className="fix-row">
            <span className="group">where</span>
            <div className="prefs-chips">
              {regions.map((r) => (
                <button
                  key={r}
                  className="chip"
                  aria-pressed={region === r}
                  onClick={() => {
                    setRegion(r);
                    setCategory("");
                  }}
                >
                  {title(r)}
                </button>
              ))}
            </div>
          </div>

          <div className="fix-row">
            <label className="group" htmlFor="missing-what">
              what
            </label>
            <select
              id="missing-what"
              value={category}
              data-changed={!!category}
              onChange={(e) => setCategory(e.target.value)}
            >
              <option value="">choose a piece…</option>
              {choices.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>

          <div className="fix-row">
            <label className="group" htmlFor="missing-note">
              note
            </label>
            <textarea
              id="missing-note"
              placeholder="optional: what it really was, if none of these fit"
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
          </div>

          {error && <p className="banner bad">{error}</p>}

          <div className="controls" style={{ marginTop: 0, borderTop: "none", paddingTop: 0 }}>
            <label className="check">
              <input
                type="checkbox"
                checked={file}
                onChange={(e) => setFile(e.target.checked)}
              />
              add it to my wardrobe too
            </label>
            <div className="spacer" />
            <button
              className="btn ghost small"
              disabled={busy}
              onClick={() => {
                setOpen(false);
                setError(null);
                setCategory("");
              }}
            >
              cancel
            </button>
            <button className="btn small" disabled={busy || !category} onClick={submit}>
              {busy && <span className="spin" />}
              record the miss
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
