import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, deleteGarment, photoUrl, setDetails, wardrobe } from "../api";
import type { Region, WardrobeItem } from "../types";
import Mannequin from "./Mannequin";
import Shop from "./Shop";
import { Wash } from "./icons";

// One shelf per region, in the order you would get dressed. The note says what
// kind of storage it is, which is the small piece of furniture language that
// makes a cabinet read as a cabinet rather than as nine identical lists.
const RAILS: { region: Region; title: string; note: string }[] = [
  { region: "head", title: "head and face", note: "hat shelf" },
  { region: "neck", title: "neck", note: "hook" },
  { region: "upper", title: "upper body", note: "hanging rail" },
  { region: "hands", title: "hands and wrists", note: "drawer" },
  { region: "waist", title: "waist", note: "belt rack" },
  { region: "lower", title: "lower body", note: "shelf" },
  { region: "full", title: "full length", note: "long rail" },
  { region: "feet", title: "feet", note: "floor rack" },
  { region: "carried", title: "carried", note: "hook" },
  { region: "unplaced", title: "unplaced", note: "no region in the ontology" },
];

/**
 * One garment on the rail: its picture, its facts, its price and how it is
 * washed, and where to buy another like it. The price and wash settings are the
 * two things the model cannot see and the owner can, so they are editable here
 * and nowhere else. A card in its own component keeps its edit state to itself,
 * so opening the editor on one garment does not disturb the next.
 */
function GarmentCard({
  item,
  sym,
  confirming,
  onConfirm,
  onRemove,
  onEdited,
  busy,
}: {
  item: WardrobeItem;
  sym: string;
  confirming: boolean;
  onConfirm: (id: string | null) => void;
  onRemove: (id: string) => void;
  onEdited: () => void;
  busy: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [price, setPrice] = useState(item.price != null ? String(item.price) : "");
  const [temp, setTemp] = useState(item.wash?.temp_c != null ? String(item.wash.temp_c) : "");
  const [cycle, setCycle] = useState(item.wash?.cycle ?? "");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const label =
    [item.color, item.material, item.category].filter(Boolean).join(" ") || "stored garment";

  async function save() {
    setSaving(true);
    setErr(null);
    try {
      const parsed = price.trim() === "" ? null : Number(price);
      if (parsed != null && (Number.isNaN(parsed) || parsed < 0)) {
        throw new ApiError(400, "price must be a number, zero or more");
      }
      await setDetails(item.id, {
        price: parsed,
        clear_price: price.trim() === "",
        wash_temp: temp.trim() === "" ? null : Number(temp),
        wash_cycle: cycle.trim() === "" ? null : cycle.trim(),
      });
      setEditing(false);
      onEdited();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  const wash = item.wash;

  return (
    <article className="garment">
      <div className="strap" aria-hidden="true" />
      <div className="frame">
        {item.photo_url ? (
          <img src={photoUrl(item.photo_url)} alt={label} loading="lazy" />
        ) : (
          <span className="no-photo">
            {item.corrected || item.category
              ? "no picture: nobody drew a box around this one"
              : "stored before pictures were kept"}
          </span>
        )}
        {item.price != null && (
          <span
            className="price-tag"
            data-estimated={item.price_source === "estimated"}
            title={
              item.price_source === "estimated"
                ? `estimated from ${item.brand ?? "the brand"}`
                : "you set this price"
            }
          >
            {sym}
            {item.price.toFixed(2)}
            {item.price_source === "estimated" && <span className="tag-est">est</span>}
          </span>
        )}
      </div>

      <div className="garment-body">
        <p className="garment-name">
          {item.category ?? "uncategorised"}
          {item.brand && <span className="brand-chip">{item.brand}</span>}
          {item.corrected && <span className="badge">corrected</span>}
        </p>
        <p className="garment-sub">
          {[item.color, item.material, item.pattern, item.sleeve]
            .filter(Boolean)
            .join(" · ") || "no attributes"}
        </p>
        <div className="garment-meta">
          {/* a bag has a warmth score and it means nothing, so the card does not
              print one: the seasons list is empty for the same reason */}
          {item.seasons.length > 0 && (
            <span className="warm">{item.warmth != null ? `${item.warmth}/11` : "?"}</span>
          )}
          {item.seasons.map((s) => (
            <span className="season" key={s.name} title={s.temp_range}>
              {s.name}
            </span>
          ))}
        </div>

        {wash && (
          <p className="wash-tag" title={wash.note}>
            <Wash />
            {wash.temp_c != null ? `${wash.temp_c}°` : "no machine wash"}
            {wash.cycle ? ` · ${wash.cycle}` : ""}
            <span className="wash-src">{wash.source}</span>
          </p>
        )}

        {editing ? (
          <div className="garment-edit">
            <label>
              price ({sym})
              <input
                type="number"
                min={0}
                step="0.01"
                value={price}
                placeholder="unset"
                onChange={(e) => setPrice(e.target.value)}
              />
            </label>
            <label>
              wash °C
              <input
                type="number"
                min={0}
                max={95}
                step={5}
                value={temp}
                placeholder="auto"
                onChange={(e) => setTemp(e.target.value)}
              />
            </label>
            <label className="wide">
              cycle
              <input
                type="text"
                value={cycle}
                placeholder="e.g. delicate"
                onChange={(e) => setCycle(e.target.value)}
              />
            </label>
            {err && <p className="edit-err">{err}</p>}
            <div className="edit-actions">
              <button className="btn small" disabled={saving} onClick={save}>
                {saving ? "saving…" : "save"}
              </button>
              <button className="btn link" onClick={() => setEditing(false)}>
                cancel
              </button>
            </div>
          </div>
        ) : (
          <Shop
            attrs={{ color: item.color, material: item.material, category: item.category }}
            compact
          />
        )}

        <div className="garment-foot">
          <span className="id">{item.id}</span>
          <span className="garment-actions">
            {!editing && (
              <button className="btn link" onClick={() => setEditing(true)}>
                edit
              </button>
            )}
            {confirming ? (
              <span className="confirm">
                <button className="btn link danger" disabled={busy} onClick={() => onRemove(item.id)}>
                  delete for good
                </button>
                <button className="btn link" onClick={() => onConfirm(null)}>
                  keep
                </button>
              </span>
            ) : (
              <button className="btn link" onClick={() => onConfirm(item.id)}>
                remove
              </button>
            )}
          </span>
        </div>
      </div>
    </article>
  );
}

export default function Wardrobe({
  enabled,
  refreshKey,
  currencySymbol,
  onChanged,
}: {
  enabled: boolean;
  refreshKey: number;
  currencySymbol: string;
  onChanged: () => void;
}) {
  const [items, setItems] = useState<WardrobeItem[] | null>(null);
  const [counts, setCounts] = useState<Partial<Record<Region, number>>>({});
  const [region, setRegion] = useState<Region | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);
  const railRef = useRef<HTMLDivElement | null>(null);

  const load = useCallback(async (which: Region | null) => {
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
  }, []);

  useEffect(() => {
    if (enabled) void load(region);
  }, [enabled, region, refreshKey, load]);

  function pick(next: Region | null) {
    setRegion(next);
    setConfirming(null);
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

  async function refresh() {
    await load(region);
    onChanged();
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
                    <GarmentCard
                      key={item.id}
                      item={item}
                      sym={currencySymbol}
                      confirming={confirming === item.id}
                      onConfirm={setConfirming}
                      onRemove={remove}
                      onEdited={refresh}
                      busy={busy}
                    />
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
