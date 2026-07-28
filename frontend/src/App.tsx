import { useCallback, useEffect, useRef, useState } from "react";
import * as api from "./api";
import { ApiError } from "./api";
import Derivation from "./components/Derivation";
import Flag from "./components/Flag";
import Insights from "./components/Insights";
import Missing from "./components/Missing";
import Preferences from "./components/Preferences";
import Profile from "./components/Profile";
import Reading from "./components/Reading";
import Recommend from "./components/Recommend";
import Shop from "./components/Shop";
import Specimen from "./components/Specimen";
import Wardrobe from "./components/Wardrobe";
import { Aperture, Auto, Moon, Sun } from "./components/icons";
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

/**
 * Three states, not two.
 *
 * "system" is the default and it is not a fallback: someone who has set their
 * machine to dark has already answered this question, and an app that opens
 * light anyway is asking them to answer it twice. It also keeps following, so
 * a machine that switches at sunset takes the app with it.
 *
 * The other two are an explicit override and are remembered, because a choice
 * that has to be made again on every reload is not a choice.
 */
type Theme = "system" | "light" | "dark";

const THEME_KEY = "fitting-room:theme";
const DARK_QUERY = "(prefers-color-scheme: dark)";

function storedTheme(): Theme {
  try {
    const saved = localStorage.getItem(THEME_KEY);
    if (saved === "light" || saved === "dark") return saved;
  } catch {
    // private browsing, or storage disabled: the system default is a fine answer
  }
  return "system";
}

/**
 * A section heading.
 *
 * `step` is the position in the analysis sequence and is only passed by the
 * three sections that are actually a sequence: a photo becomes a reading
 * becomes the arithmetic behind it. The wardrobe and what to wear are places
 * you go, not steps you take, so numbering them would be grammar rather than
 * information.
 *
 * `state` is a live readout — how many garments were found, whether the
 * wardrobe is reachable. It is left off when the only thing it could do is
 * restate the title in smaller type.
 */
function Section({
  step,
  title,
  state,
  children,
}: {
  step?: string;
  title: string;
  state?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="section" data-stepped={step ? "true" : undefined}>
      <div className="section-head">
        {step && <span className="n">{step}</span>}
        <h2>{title}</h2>
        {state && <span className="aside">{state}</span>}
      </div>
      {children}
    </section>
  );
}

export default function App() {
  const [theme, setTheme] = useState<Theme>(storedTheme);
  const [systemDark, setSystemDark] = useState(
    () => typeof window !== "undefined" && window.matchMedia(DARK_QUERY).matches
  );
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

  // On "system" the attribute is removed entirely rather than set to whatever
  // the machine currently is, so the stylesheet's own media query does the
  // work and native controls get the right color-scheme with it.
  useEffect(() => {
    const root = document.documentElement;
    if (theme === "system") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", theme);
    try {
      if (theme === "system") localStorage.removeItem(THEME_KEY);
      else localStorage.setItem(THEME_KEY, theme);
    } catch {
      // storage refused: the choice still holds for this session
    }
  }, [theme]);

  // keep following the machine while no explicit choice is in force
  useEffect(() => {
    const mq = window.matchMedia(DARK_QUERY);
    const onChange = (e: MediaQueryListEvent) => setSystemDark(e.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

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
      else setError("Lost contact with the analyser while reading that photo.");
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
  // the icon shows the state, the label says what pressing it does next
  const themeLabel =
    theme === "system"
      ? `following your machine (${systemDark ? "dark" : "light"}) — press for light`
      : theme === "light"
        ? "light — press for dark"
        : "dark — press to follow your machine again";
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
          <p>garment collection · determined locally</p>
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
            aria-label={themeLabel}
            title={themeLabel}
            onClick={() =>
              setTheme((t) =>
                t === "system" ? "light" : t === "light" ? "dark" : "system"
              )
            }
          >
            {theme === "system" ? <Auto /> : theme === "dark" ? <Moon /> : <Sun />}
          </button>
        </div>
      </header>

      {conn === "down" && (
        <p className="banner bad" role="status">
          Fitting Room cannot reach the part of itself that reads photographs, so
          nothing can be analysed yet. Start it with{" "}
          <code>uvicorn api:app --port 8000</code> and this page unlocks on its
          own — there is nothing to click here.
        </p>
      )}

      {conn === "up" && health && !health.neo4j && (
        <p className="banner warn" role="status">
          Your wardrobe is not open, so garments cannot be kept and nothing can be
          recommended. Reading a photograph still works, and the weather it
          reports is derived from the same table the wardrobe uses. Open it with{" "}
          <code>docker compose up -d</code>.
        </p>
      )}

      {view === "admin" ? (
        <Section title="Admin statistics" state="the whole graph, not one wardrobe">
          <p className="prose" style={{ marginBottom: 18 }}>
            Everything countable across every stored garment and every
            correction. This is the maintainer's view; the numbers describe the
            contents of the database, never the accuracy of the model, which is
            measured separately by <code>evaluate.py</code>.
          </p>
          <Insights data={graphUp ? insightData : null} />
        </Section>
      ) : (
        <>
      <div className="columns">
        <div>
          <Section step="01" title="Specimen" state={file ? "ready to read" : undefined}>
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
                  ? "Warming up. The first photograph of a session waits 20 to 40 seconds while the recogniser loads; every one after it takes about three."
                  : "Reading the photograph, about three seconds."}
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
            step="02"
            title="Determination"
            state={
              result
                ? result.count > 1
                  ? `${result.count} garments found`
                  : undefined
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

                {/* everything the system saw and would not swear to, in its own
                    words, followed by the way to tell it what it never saw */}
                {result.notes.length > 0 && (
                  <div className="panel observations">
                    <p className="obs-head">what was seen but not written down</p>
                    <ul>
                      {result.notes.map((note, i) => (
                        <li key={i}>{note}</li>
                      ))}
                    </ul>
                  </div>
                )}

                <Missing
                  analysisId={result.analysis_id}
                  ontology={ontology}
                  onReported={refreshAll}
                />
              </div>
            ) : (
              <div className="panel">
                <p className="reading-empty">
                  Mount a photograph on the left and a determination label is
                  typed here: a category, a material, a warmth from 1 to 11 and
                  the seasons that warmth falls into, each with the confidence
                  behind it. Nothing here is guessed by the browser, and nothing
                  you later revise is erased.
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
        step="03"
        title="Derivation"
        state={result && result.count > 1 ? "for the main piece" : undefined}
      >
        {result && result.garments[0] && ontology ? (
          <Derivation analysis={result.garments[0]} ontology={ontology} />
        ) : (
          <div className="panel">
            <p className="reading-empty">
              What is underneath the label. The weather is not predicted, it is
              derived: material warmth plus category warmth, adjusted for
              sleeves, matched against the season windows. Read a photograph and
              the arithmetic for it appears here.
            </p>
          </div>
        )}
      </Section>

      <Section title="Wardrobe" state={graphUp ? undefined : "not open"}>
        <Wardrobe
          enabled={graphUp}
          refreshKey={refreshKey}
          currencySymbol={symbol}
          onChanged={refreshAll}
        />
      </Section>

      <Section title="What to wear" state={graphUp ? undefined : "not open"}>
        <Recommend enabled={graphUp} ontology={ontology} refreshKey={refreshKey} />
        <details className="prefs-disclosure">
          <summary>tune your preferences</summary>
          <Preferences enabled={graphUp} ontology={ontology} onSaved={refreshAll} />
        </details>
      </Section>

      <Section title="Your wardrobe" state={graphUp ? undefined : "not open"}>
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
