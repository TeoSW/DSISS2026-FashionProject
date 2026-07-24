import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, deleteGarment, photoUrl, wardrobe } from "../api";
import type { Region, WardrobeItem } from "../types";
import Mannequin from "./Mannequin";

const RAILS: { region: Region; title: string; note: string }[] = [
  { region: "upper", title: "upper body", note: "hanging rail" },
  { region: "lower", title: "lower body", note: "shelf" },
  { region: "full", title: "full length", note: "long rail" },
  { region: "unplaced", title: "unplaced", note: "no region in the ontology" },
];

/**
 * The wardrobe.
 *
 * A stored garment is a photograph and a handful of facts, so the card shows the
 * photograph. The twelve-character id is still on it, in small type, because
 * that is what the graph calls this thing and hiding it would make the two
 * views of the same garment impossible to line up.
 *
 * Deleting takes two clicks and no modal. A dialogue that steals focus to ask
 * "are you sure" for one garment out of a wardrobe is heavier than the action
 * deserves; a button that changes into its own confirmation is not.
 */
export default function Wardrobe({
  enabled,
  refreshKey,
  onChanged,
}: {
  enabled: boolean;
  refreshKey: number;
  onChanged: () => void;
}) {
  const [items, setItems] = useState<WardrobeItem[] | null>(null);
  const [counts, setCounts] = useState<Partial<Record<Region, number>>>({});
  const [region, setRegion] = useState<Region | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);
  const railRef = useRef<HTMLDivElement | null>(null);

  const load = useCallback(
    async (which: Region | null) => {
      setBusy(true);
      setError(null);
      try {
        const res = await wardrobe(which);
        setItems(res.items);
        setCounts(res.regions);
      } catch (e) {
        setError(e instanceof ApiError ? e.message : String(e));
        setItems(null);
      } finally {
        setBusy(false);
      }
    },
    []
  );

  useEffect(() => {
    if (enabled) void load(region);
  }, [enabled, region, refreshKey, load]);

  function pick(next: Region | null) {
    setRegion(next);
    setConfirming(null);
    // "in the same page": the rail is already below the figure, so bring it
    // into view rather than navigating anywhere
    if (next) {
      requestAnimationFrame(() =>
        railRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })
      );
    }
  }

  async function remove(id: string) {
    setBusy(true);
    try {
      await deleteGarment(id);
      setConfirming(null);
      await load(region);
      onChanged();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  if (!enabled) {
    return (
      <p className="banner">
        Neo4j is not reachable, so the wardrobe is empty of necessity, not of
        content. Analysis still works without it.
      </p>
    );
  }

  const shown = items ?? [];
  const rails = region ? RAILS.filter((r) => r.region === region) : RAILS;

  return (
    <div className="wardrobe">
      <div className="cabinet">
        <Mannequin counts={counts} active={region} onPick={pick} />

        <div className="rails" ref={railRef}>
          {error && <p className="banner bad">{error}</p>}

          {shown.length === 0 && !busy && (
            <p className="banner">
              {region
                ? `nothing on the ${region} rail yet`
                : "the wardrobe is empty. Analyse a photo with “save to the knowledge graph” ticked and it will hang here."}
            </p>
          )}

          {rails.map(({ region: r, title, note }) => {
            const group = shown.filter((i) => i.region === r);
            if (group.length === 0) return null;
            return (
              <section className="rail" key={r}>
                <div className="rail-head">
                  <span className="rail-title">{title}</span>
                  <span className="rail-note">{note}</span>
                  <span className="rail-n">{group.length}</span>
                </div>
                <div className="rail-bar" aria-hidden="true" />
                <div className="hangers">
                  {group.map((item) => (
                    <article className="garment" key={item.id}>
                      <div className="hook" aria-hidden="true" />
                      <div className="frame">
                        {item.photo_url ? (
                          <img
                            src={photoUrl(item.photo_url)}
                            alt={
                              [item.color, item.material, item.category]
                                .filter(Boolean)
                                .join(" ") || "stored garment"
                            }
                            loading="lazy"
                          />
                        ) : (
                          <span className="no-photo">
                            stored before pictures were kept
                          </span>
                        )}
                      </div>

                      <div className="garment-body">
                        <p className="garment-name">
                          {item.category ?? "uncategorised"}
                          {item.corrected && <span className="badge">corrected</span>}
                        </p>
                        <p className="garment-sub">
                          {[item.color, item.material, item.sleeve]
                            .filter(Boolean)
                            .join(" · ") || "no attributes"}
                        </p>
                        <div className="garment-meta">
                          <span className="warm">
                            {item.warmth != null ? `${item.warmth}/11` : "?"}
                          </span>
                          {item.seasons.map((s) => (
                            <span className="season" key={s.name} title={s.temp_range}>
                              {s.name}
                            </span>
                          ))}
                        </div>
                        <div className="garment-foot">
                          <span className="id">{item.id}</span>
                          {confirming === item.id ? (
                            <span className="confirm">
                              <button
                                className="btn link danger"
                                disabled={busy}
                                onClick={() => remove(item.id)}
                              >
                                delete for good
                              </button>
                              <button
                                className="btn link"
                                onClick={() => setConfirming(null)}
                              >
                                keep
                              </button>
                            </span>
                          ) : (
                            <button
                              className="btn link"
                              onClick={() => setConfirming(item.id)}
                            >
                              remove
                            </button>
                          )}
                        </div>
                      </div>
                    </article>
                  ))}
                </div>
              </section>
            );
          })}

          {busy && <p className="reading-empty">querying the graph</p>}
        </div>
      </div>
    </div>
  );
}
