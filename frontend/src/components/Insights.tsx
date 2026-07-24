import type { Insights as Data, Tally } from "../types";

/**
 * Statistics about what is in the wardrobe.
 *
 * Every number here is a count of stored garments, not a measure of how good
 * the model is: accuracy needs labelled ground truth and is measured by
 * evaluate.py against Fashionpedia. A wardrobe can only tell you what it
 * contains, and the panel says so rather than letting a big confident number
 * be mistaken for a score.
 *
 * One accent colour throughout, because every chart here has a single series.
 * A palette of six hues for six bars of the same measurement would be
 * decoration pretending to be information.
 */

function Tile({ k, v, note }: { k: string; v: string; note?: string }) {
  return (
    <div className="tile">
      <span className="tile-k">{k}</span>
      <span className="tile-v">{v}</span>
      {note && <span className="tile-note">{note}</span>}
    </div>
  );
}

function Bars({
  rows,
  max,
  suffix,
  swatch,
}: {
  rows: Tally[];
  max: number;
  suffix?: (row: Tally) => string;
  swatch?: boolean;
}) {
  if (rows.length === 0) return <p className="reading-empty">nothing stored yet</p>;
  return (
    <div className="bars">
      {rows.map((row) => (
        <div className="bar-row" key={row.name}>
          <span className="bar-label">
            {swatch && <span className="swatch" data-color={row.name} />}
            {row.name}
          </span>
          <span className="bar-track">
            <span
              className="bar-fill"
              style={{ width: `${max ? Math.max(1.5, (row.n / max) * 100) : 0}%` }}
            />
          </span>
          <span className="bar-n">{row.n}</span>
          <span className="bar-extra">{suffix ? suffix(row) : ""}</span>
        </div>
      ))}
    </div>
  );
}

function Panel({ title, note, children }: { title: string; note?: string; children: React.ReactNode }) {
  return (
    <div className="panel stat-panel">
      <div className="stat-head">
        <h3>{title}</h3>
        {note && <span className="aside">{note}</span>}
      </div>
      {children}
    </div>
  );
}

export default function Insights({ data }: { data: Data | null }) {
  if (!data) {
    return <p className="reading-empty">statistics load with the graph</p>;
  }

  const g = data.graph;
  const t = g.totals;
  const maxCat = Math.max(1, ...g.by_category.map((r) => r.n));
  const maxMat = Math.max(1, ...g.by_material.map((r) => r.n));
  const maxColor = Math.max(1, ...g.by_color.map((r) => r.n));
  const maxSeason = Math.max(1, ...g.by_season.map((r) => r.n));
  const maxWarmth = Math.max(1, ...g.warmth.map((r) => r.n));
  const pct = (x: number | null | undefined) =>
    x == null ? "n/a" : `${(x * 100).toFixed(1)}%`;
  const mb = (bytes: number) => `${(bytes / 1024 / 1024).toFixed(1)}MB`;

  const confusions = data.corrections?.confusions ?? [];

  return (
    <div className="stats">
      <div className="tiles">
        <Tile k="garments stored" v={String(t.garments)} note={`${data.photos.files} pictures, ${mb(data.photos.bytes)}`} />
        <Tile
          k="mean warmth"
          v={t.mean_warmth != null ? `${t.mean_warmth.toFixed(1)}/11` : "n/a"}
          note="material + category + sleeve"
        />
        <Tile
          k="mean confidence"
          v={pct(t.mean_confidence)}
          note={`${t.low_confidence_edges} of ${t.attribute_edges} edges below 40%`}
        />
        <Tile
          k="judged"
          v={String(data.feedback.total)}
          note={
            data.feedback.agreement != null
              ? `${pct(data.feedback.agreement)} confirmed by a person`
              : "nobody has flagged a reading yet"
          }
        />
        <Tile
          k="human answers"
          v={String(t.human_edges)}
          note="attribute edges a person overwrote"
        />
        <Tile k="checkpoint" v={data.model.split("/").pop() ?? data.model} note={data.model} />
      </div>

      <div className="stat-grid">
        <Panel title="By category" note="what is on the rails">
          <Bars
            rows={g.by_category}
            max={maxCat}
            suffix={(r) =>
              `${r.region ?? ""}${r.confidence != null ? ` · ${pct(r.confidence)}` : ""}`
            }
          />
        </Panel>

        <Panel title="By material" note="with its warmth weight">
          <Bars
            rows={g.by_material}
            max={maxMat}
            suffix={(r) => (r.warmth != null ? `warmth ${r.warmth}` : "")}
          />
        </Panel>

        <Panel title="By colour" note="as the model called it">
          <Bars rows={g.by_color} max={maxColor} swatch />
        </Panel>

        <Panel title="By style">
          <Bars rows={g.by_style} max={Math.max(1, ...g.by_style.map((r) => r.n))} />
        </Panel>

        <Panel title="Warmth distribution" note="1 cools you down, 11 is for freezing">
          {g.warmth.length === 0 ? (
            <p className="reading-empty">nothing stored yet</p>
          ) : (
            <div className="histogram">
              {Array.from({ length: 11 }, (_, i) => i + 1).map((score) => {
                const row = g.warmth.find((w) => w.warmth === score);
                const n = row?.n ?? 0;
                return (
                  <div className="col" key={score} title={`${n} at ${score}/11`}>
                    <span className="col-n">{n || ""}</span>
                    <span
                      className="col-fill"
                      data-empty={n === 0}
                      style={{ height: `${(n / maxWarmth) * 100}%` }}
                    />
                    <span className="col-k">{score}</span>
                  </div>
                );
              })}
            </div>
          )}
        </Panel>

        <Panel title="Season coverage" note="windows overlap on purpose">
          <Bars
            rows={g.by_season}
            max={maxSeason}
            suffix={(r) => r.temp_range ?? ""}
          />
        </Panel>

        <Panel
          title="What people corrected"
          note={
            data.corrections
              ? `${data.corrections.wrong} corrections, ${data.corrections.confirmed} confirmations`
              : "graph unavailable"
          }
        >
          {confusions.length === 0 ? (
            <p className="reading-empty">
              No corrections yet. Flag a wrong reading and the pair shows up here.
            </p>
          ) : (
            <div className="confusions">
              {confusions.map((c) => (
                <div className="confusion" key={`${c.group}-${c.predicted}-${c.actual}`}>
                  <span className="group">{c.group}</span>
                  <span className="was">{c.predicted}</span>
                  <span className="arrow" aria-hidden="true">
                    →
                  </span>
                  <span className="is">{c.actual}</span>
                  <span className="bar-n">{c.n}</span>
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>

      <p className="prose">
        These are the contents of one wardrobe, not a score. Accuracy is measured
        separately, on Fashionpedia's labelled validation split, by{" "}
        <code>evaluate.py</code>; a confident-looking count of stored garments
        says nothing about whether the labels on them are right. What is useful
        here is the correction table: it names the pair of labels worth spending
        the next round of work on.
      </p>
    </div>
  );
}
