import { useCallback, useEffect, useRef, useState } from "react";
import * as api from "./api";
import { ApiError } from "./api";
import Derivation from "./components/Derivation";
import Flag from "./components/Flag";
import Insights from "./components/Insights";
import Reading from "./components/Reading";
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
  const [conn, setConn] = useState<Conn>("connecting");
  const [health, setHealth] = useState<Health | null>(null);
  const [ontology, setOntology] = useState<Ontology | null>(null);
  const [graphStats, setGraphStats] = useState<GraphStats | null>(null);
  const [feedbackStats, setFeedbackStats] = useState<FeedbackStats | null>(null);
  const [insightData, setInsightData] = useState<InsightData | null>(null);

  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [save, setSave] = useState(false);

  const [phase, setPhase] = useState<Phase>("idle");
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
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

  // called whenever the stored world changed: a garment saved, corrected or
  // removed. Each is independent, so a failing one must not blank the others.
  const refreshCounters = useCallback(() => {
    api.graphStats().then(setGraphStats).catch(() => undefined);
    api.feedbackStats().then(setFeedbackStats).catch(() => undefined);
    api.insights().then(setInsightData).catch(() => undefined);
  }, []);

  useEffect(() => {
    void check();
  }, [check]);

  // while the backend is down, keep looking: the usual fix is the person
  // starting uvicorn in another window, and the page should notice by itself
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
    setAnalysis(null);
    setPhase(rejection ? "error" : "idle");
    setError(rejection ?? null);
  }

  async function analyse() {
    if (!file) return;
    setPhase("working");
    setError(null);
    setAnalysis(null);
    try {
      const result = await api.analyze(file, save && !!health?.neo4j);
      setAnalysis(result);
      setPhase("done");
      analysed.current += 1;
      if (result.saved) {
        setRefreshKey((k) => k + 1);
        refreshCounters();
      }
    } catch (e) {
      setPhase("error");
      if (e instanceof ApiError) setError(e.message);
      else setError("could not reach the backend. Is uvicorn still running?");
      void check();
    }
  }

  const busy = phase === "working";
  const graphUp = conn === "up" && !!health?.neo4j;
  const corrections = feedbackStats?.corpus.total ?? 0;

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
          Neo4j is not reachable, so saving and the library are switched off.
          Analysis works: the weather falls back to the same table the graph is
          seeded from. Start it with <code>docker compose up -d</code>.
        </p>
      )}

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
            aside={analysis ? "from the api" : "awaiting a specimen"}
          >
            {analysis ? (
              <Reading analysis={analysis} original={preview}>
                <Flag
                  // a new analysis is a new judgement: keying on the id throws
                  // away the previous receipt instead of showing it under a
                  // photo it has nothing to do with
                  key={analysis.analysis_id}
                  analysis={analysis}
                  ontology={ontology}
                  onApplied={(result) => {
                    if (result.garment_updated) {
                      setAnalysis({
                        ...analysis,
                        // a correction can also be what files the garment in
                        // the first place, so the id may arrive here
                        id: result.garment_id ?? analysis.id,
                        saved: analysis.saved || result.filed,
                        warmth: result.warmth ?? analysis.warmth,
                        layer: result.layer ?? analysis.layer,
                        seasons: result.seasons,
                        tags: Object.fromEntries(
                          Object.entries(analysis.tags).map(([g, t]) => [
                            g,
                            result.corrections[g]
                              ? { label: result.corrections[g], confidence: 1 }
                              : t,
                          ])
                        ),
                      });
                      setRefreshKey((k) => k + 1);
                    }
                    refreshCounters();
                  }}
                />
              </Reading>
            ) : (
              <div className="panel">
                <p className="reading-empty">
                  Drop a photo on the left. The API returns a category, a material,
                  a warmth number from 1 to 11 and the seasons that number falls
                  into. Nothing on this page is guessed by the browser.
                </p>
                <ul className="steps">
                  <li>
                    <b>01</b> background removed
                  </li>
                  <li>
                    <b>02</b> category · material · sleeve · colour · style
                  </li>
                  <li>
                    <b>03</b> warmth arithmetic, then the season windows
                  </li>
                  <li>
                    <b>04</b> flag anything wrong, it is filed under your answer
                  </li>
                </ul>
              </div>
            )}
          </Section>
        </div>
      </div>

      {/* always rendered, even empty: the numbers are the procedure, and a
          sequence that skips 03 until something happens is a worse sequence */}
      <Section n="03" title="Derivation" aside="why that weather">
        {analysis && ontology ? (
          <Derivation analysis={analysis} ontology={ontology} />
        ) : (
          <div className="panel">
            <p className="reading-empty">
              The weather is not predicted, it is derived: material warmth plus
              category warmth, adjusted for sleeves, matched against the season
              windows. Analyse a photo and the arithmetic for it appears here.
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
          onChanged={refreshCounters}
        />
      </Section>

      <Section n="05" title="Statistics" aside="what is stored, not how good it is">
        <Insights data={graphUp ? insightData : null} />
      </Section>

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
        <span>every label and season on this page came back from the api</span>
      </footer>
    </div>
  );
}
