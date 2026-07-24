import { useCallback, useEffect, useRef, useState } from "react";
import * as api from "./api";
import { ApiError } from "./api";
import Derivation from "./components/Derivation";
import Flag from "./components/Flag";
import Insights from "./components/Insights";
import Preferences from "./components/Preferences";
import Profile from "./components/Profile";
import Reading from "./components/Reading";
import Recommend from "./components/Recommend";
import Shop from "./components/Shop";
import Specimen from "./components/Specimen";
import Wardrobe from "./components/Wardrobe";
import { Aperture, Moon, Sun } from "./components/icons";
import type {
  Analysis,
  FeedbackStats,
  GraphStats,
  Health,
  Insights as InsightData,
  Ontology,
} from "./types";

type Conn = "connecting" | "up" | "down";
type Phase = "idle" | "working" | "done" | "error";
type View = "app" | "admin";

function Section({
  n,
  title,
  aside,
  children,
}: {
  n: string;
  title: string;
  aside?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="section">
      <div className="section-head">
        <span className="n">{n}</span>
        <h2>{title}</h2>
        {aside && <span className="aside">{aside}</span>}
      </div>
      {children}
    </section>
  );
}

export default function App() {
  const [theme, setTheme] = useState<"light" | "dark" | null>(null);
  const [view, setView] = useState<View>(() =>
    window.location.hash.includes("admin") ? "admin" : "app"
  );
  const [conn, setConn] = useState<Conn>("connecting");
  const [health, setHealth] = useState<Health | null>(null);
  const [ontology, setOntology] = useState<Ontology | null>(null);
  const [graphStats, setGraphStats] = useState<GraphStats | null>(null);
  const [feedbackStats, setFeedbackStats] = useState<FeedbackStats | null>(null);
  const [insightData, setInsightData] = useState<InsightData | null>(null);

  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [save, setSave] = useState(false);
  const [brand, setBrand] = useState("");

  const [phase, setPhase] = useState<Phase>("idle");
  const [result, setResult] = useState<Analysis | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  // the first /analyze of a session pays for loading 600MB of weights; every
  // later one takes about three seconds. Saying which is which is the
  // difference between a slow app and an app that looks hung.
  const analysed = useRef(0);

  useEffect(() => {
    if (theme) document.documentElement.setAttribute("data-theme", theme);
    else document.documentElement.removeAttribute("data-theme");
  }, [theme]);

  // the admin statistics live on their own page, reachable at #/admin so a
  // deep link and the browser's back button both work without a router
  useEffect(() => {
    const onHash = () =>
      setView(window.location.hash.includes("admin") ? "admin" : "app");
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  function goto(next: View) {
    window.location.hash = next === "admin" ? "/admin" : "/";
    setView(next);
  }

  const check = useCallback(async () => {
    try {
      const h = await api.health();
      setHealth(h);
      setConn("up");
      const [o, s] = await Promise.allSettled([api.ontology(), api.graphStats()]);
      if (o.status === "fulfilled") setOntology(o.value);
      if (s.status === "fulfilled") setGraphStats(s.value);
      api.feedbackStats().then(setFeedbackStats).catch(() => undefined);
      api.insights().then(setInsightData).catch(() => undefined);
    } catch {
      setConn("down");
      setHealth(null);
    }
  }, []);

  // called whenever the stored world changed: a garment saved, corrected,
  // priced or removed. Each is independent, so a failing one must not blank the
  // others, and bumping refreshKey re-pulls the wardrobe, profile and outfit.
  const refreshAll = useCallback(() => {
    setRefreshKey((k) => k + 1);
    api.graphStats().then(setGraphStats).catch(() => undefined);
    api.feedbackStats().then(setFeedbackStats).catch(() => undefined);
    api.insights().then(setInsightData).catch(() => undefined);
  }, []);

  useEffect(() => {
    void check();
  }, [check]);

  useEffect(() => {
    if (conn !== "down") return;
    const timer = setInterval(check, 8000);
    return () => clearInterval(timer);
  }, [conn, check]);

  useEffect(() => {
    if (!file) {
      setPreview(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  function pick(next: File | null, rejection?: string) {
    setFile(next);
    setResult(null);
    setPhase(rejection ? "error" : "idle");
    setError(rejection ?? null);
  }

  async function analyse() {
    if (!file) return;
    setPhase("working");
    setError(null);
    setResult(null);
    try {
      const res = await api.analyze(file, save && !!health?.neo4j, brand);
      setResult(res);
      setPhase("done");
      analysed.current += 1;
      if (res.garments.some((g) => g.saved)) refreshAll();
    } catch (e) {
      setPhase("error");
      if (e instanceof ApiError) setError(e.message);
      else setError("could not reach the backend. Is uvicorn still running?");
      void check();
    }
  }

  // one garment out of the current upload was corrected: replace just that
  // garment in the list, leaving its siblings and the upload as they were
  function applyFeedback(
    analysisId: string,
    fb: import("./types").FeedbackResult
  ) {
    setResult((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        garments: prev.garments.map((g) => {
          if (g.analysis_id !== analysisId || !fb.garment_updated) return g;
          return {
            ...g,
            id: fb.garment_id ?? g.id,
            saved: g.saved || fb.filed,
            warmth: fb.warmth ?? g.warmth,
            layer: fb.layer ?? g.layer,
            seasons: fb.seasons,
            tags: Object.fromEntries(
              Object.entries(g.tags).map(([grp, t]) => [
                grp,
                fb.corrections[grp]
                  ? { label: fb.corrections[grp], confidence: 1 }
                  : t,
              ])
            ),
          };
        }),
      };
    });
    refreshAll();
  }

  const busy = phase === "working";
  const graphUp = conn === "up" && !!health?.neo4j;
  const corrections = feedbackStats?.corpus.total ?? 0;
  const symbol = ontology?.currency_symbol ?? "€";

  return (
    <div className="app">
      <header className="top">
        <span className="mark">
          <Aperture />
        </span>
        <div className="wordmark">
          <h1>Fitting Room</h1>
          <p>garment · instrument</p>
        </div>

        <nav className="viewnav" aria-label="section">
          <button aria-pressed={view === "app"} onClick={() => goto("app")}>
            Wardrobe
          </button>
          <button aria-pressed={view === "admin"} onClick={() => goto("admin")}>
            Admin
          </button>
        </nav>

        <div className="top-right">
          <span className="pill" data-state={conn}>
            <span className="dot" />
            {conn === "up"
              ? health?.model ?? "connected"
              : conn === "down"
                ? "backend unreachable"
                : "connecting"}
          </span>
          <button
            className="icon-btn"
            aria-label="switch between light and dark"
            onClick={() =>
              setTheme((t) => {
                const current =
                  t ??
                  (window.matchMedia("(prefers-color-scheme: dark)").matches
                    ? "dark"
                    : "light");
                return current === "dark" ? "light" : "dark";
              })
            }
          >
            {theme === "dark" ? <Sun /> : <Moon />}
          </button>
        </div>
      </header>

      {conn === "down" && (
        <p className="banner bad" role="status">
          The backend is not answering at <code>{api.BASE}</code>. Start it with{" "}
          <code>uvicorn api:app --port 8000</code> and this page will unlock by
          itself.
        </p>
      )}

      {conn === "up" && health && !health.neo4j && (
        <p className="banner warn" role="status">
          Neo4j is not reachable, so saving, the wardrobe and the recommender are
          switched off. Analysis works: the weather falls back to the same table
          the graph is seeded from. Start it with <code>docker compose up -d</code>.
        </p>
      )}

      {view === "admin" ? (
        <>
          <Section
            n="—"
            title="Admin statistics"
            aside="the whole graph, not one wardrobe"
          >
            <p className="prose" style={{ marginBottom: 18 }}>
              Everything countable across every stored garment and every
              correction. This is the maintainer's view; the numbers describe the
              contents of the database, never the accuracy of the model, which is
              measured separately by <code>evaluate.py</code>.
            </p>
            <Insights data={graphUp ? insightData : null} />
          </Section>
        </>
      ) : (
        <>
          <div className="columns">
            <div>
              <Section n="01" title="Specimen" aside="one garment photo">
                <Specimen
                  file={file}
                  preview={preview}
                  disabled={conn !== "up"}
                  busy={busy}
                  save={save}
                  canSave={graphUp}
                  brand={brand}
                  onBrandChange={setBrand}
                  onPick={pick}
                  onSaveChange={setSave}
                  onAnalyse={analyse}
                />
                {busy && (
                  <p className="banner" role="status">
                    {analysed.current === 0
                      ? "loading the model into memory. This happens once per server start and takes 20 to 40 seconds."
                      : "analysing, about three seconds."}
                  </p>
                )}
                {phase === "error" && error && (
                  <p className="banner bad" role="alert">
                    {error}
                  </p>
                )}
              </Section>
            </div>

            <div>
              <Section
                n="02"
                title="Reading"
                aside={
                  result
                    ? result.count > 1
                      ? `${result.count} garments found`
                      : "from the api"
                    : "awaiting a specimen"
                }
              >
                {result ? (
                  <div className="analysis-stack">
                    {result.count > 1 && (
                      <p className="banner" role="status">
                        {result.count} garments found in this photo. Each is
                        segmented, analysed and, if saved, stored on its own.
                      </p>
                    )}
                    {preview && (
                      <figure className="uploaded">
                        <img src={preview} alt="the photo as uploaded" />
                        <figcaption>as uploaded — the wearer is removed below</figcaption>
                      </figure>
                    )}
                    {result.garments.map((g) => (
                      <Reading
                        key={g.analysis_id}
                        garment={g}
                        multi={result.count > 1}
                        currencySymbol={symbol}
                      >
                        <Flag
                          analysis={g}
                          ontology={ontology}
                          onApplied={(fb) => applyFeedback(g.analysis_id, fb)}
                        />
                        <Shop
                          attrs={{
                            color: g.tags.color?.label,
                            material: g.tags.material?.label,
                            category: g.tags.category?.label,
                          }}
                        />
                      </Reading>
                    ))}
                  </div>
                ) : (
                  <div className="panel">
                    <p className="reading-empty">
                      Drop a photo on the left. The API returns a category, a
                      material, a warmth number from 1 to 11 and the seasons that
                      number falls into. Nothing on this page is guessed by the
                      browser.
                    </p>
                    <ul className="steps">
                      <li>
                        <b>01</b> only the clothing is kept, the wearer removed
                      </li>
                      <li>
                        <b>02</b> each garment in the photo, segmented apart
                      </li>
                      <li>
                        <b>03</b> category · material · sleeve · colour · style
                      </li>
                      <li>
                        <b>04</b> warmth arithmetic, then the season windows
                      </li>
                    </ul>
                  </div>
                )}
              </Section>
            </div>
          </div>

          <Section
            n="03"
            title="Derivation"
            aside={result && result.count > 1 ? "for the main piece" : "why that weather"}
          >
            {result && result.garments[0] && ontology ? (
              <Derivation analysis={result.garments[0]} ontology={ontology} />
            ) : (
              <div className="panel">
                <p className="reading-empty">
                  The weather is not predicted, it is derived: material warmth
                  plus category warmth, adjusted for sleeves, matched against the
                  season windows. Analyse a photo and the arithmetic for it
                  appears here.
                </p>
              </div>
            )}
          </Section>

          <Section
            n="04"
            title="Wardrobe"
            aside={graphUp ? "click a part of the body" : "graph offline"}
          >
            <Wardrobe
              enabled={graphUp}
              refreshKey={refreshKey}
              currencySymbol={symbol}
              onChanged={refreshAll}
            />
          </Section>

          <Section n="05" title="What to wear" aside="from your wardrobe and taste">
            <Recommend enabled={graphUp} ontology={ontology} refreshKey={refreshKey} />
            <details className="prefs-disclosure">
              <summary>tune your preferences</summary>
              <Preferences enabled={graphUp} ontology={ontology} onSaved={refreshAll} />
            </details>
          </Section>

          <Section n="06" title="Your wardrobe" aside="style, value, and the gaps">
            <Profile enabled={graphUp} refreshKey={refreshKey} />
          </Section>
        </>
      )}

      <footer className="foot">
        <span>
          model <b>{health?.model ?? "unknown"}</b>
        </span>
        <span>
          graph <b>{graphStats ? (graphStats.nodes.Garment ?? 0) : 0}</b> garments,{" "}
          <b>
            {graphStats
              ? Object.values(graphStats.relationships).reduce((a, b) => a + b, 0)
              : 0}
          </b>{" "}
          edges
        </span>
        <span>
          corrections <b>{corrections}</b>
          {feedbackStats?.corpus.agreement != null &&
            ` · ${Math.round(feedbackStats.corpus.agreement * 100)}% confirmed`}
        </span>
        <span>every label, price and season here came from the api or from you</span>
      </footer>
    </div>
  );
}
