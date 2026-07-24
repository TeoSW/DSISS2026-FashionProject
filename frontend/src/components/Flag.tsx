import { useState } from "react";
import { ApiError, sendFeedback } from "../api";
import type { FeedbackResult, GarmentResult, Ontology } from "../types";
import { GROUPS } from "../types";

/**
 * The correction loop, from the person's side.
 *
 * Two buttons, because a confirmation is signal too and costs one click, and a
 * correction form built from /ontology so the answer is always a label the
 * system can actually store. Free text is available as a note for the case the
 * ontology has no word for what this garment is, which is a real answer and
 * worth collecting even though no classifier can learn from it directly.
 *
 * What the receipt says afterwards is deliberately literal. The correction is
 * on disk and in the graph immediately; the model is not retrained by pressing
 * a button, and the interface does not imply that it was.
 */
export default function Flag({
  analysis,
  ontology,
  onApplied,
}: {
  analysis: GarmentResult;
  ontology: Ontology | null;
  onApplied: (result: FeedbackResult) => void;
}) {
  const [mode, setMode] = useState<"ask" | "fixing" | "sent">("ask");
  const [fixes, setFixes] = useState<Record<string, string>>({});
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [receipt, setReceipt] = useState<FeedbackResult | null>(null);
  // what the model had said, snapshotted before the correction is applied:
  // the receipt has to show "knit -> cotton", and by the time it renders the
  // analysis on screen already carries the corrected labels
  const [before, setBefore] = useState<Record<string, string>>({});

  const groups = GROUPS.filter((g) => analysis.tags[g] && ontology?.attributes[g]);
  const changed = Object.entries(fixes).filter(
    ([g, v]) => v && v !== analysis.tags[g]?.label
  );

  async function submit(verdict: "correct" | "wrong") {
    setBusy(true);
    setError(null);
    setBefore(
      Object.fromEntries(groups.map((g) => [g, analysis.tags[g].label]))
    );
    try {
      const result = await sendFeedback({
        analysis_id: analysis.analysis_id,
        verdict,
        corrections: verdict === "wrong" ? Object.fromEntries(changed) : {},
        note: note.trim(),
      });
      setReceipt(result);
      setMode("sent");
      onApplied(result);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  if (mode === "sent" && receipt) {
    return (
      <div className="flag">
        <div className="receipt">
          <span>
            <b>recorded</b> as {receipt.id}
            {receipt.verdict === "correct" ? " (confirmed)" : " (corrected)"}
          </span>
          {Object.entries(receipt.corrections).map(([g, v]) => (
            <span key={g}>
              {g}: {before[g] ?? "?"} → {v}
            </span>
          ))}
          <span>
            {receipt.graph_updated
              ? "correction node written to neo4j"
              : "neo4j unreachable, kept on disk only"}
          </span>
          {receipt.garment_updated && (
            <span>
              garment re-derived: warmth {receipt.warmth}/11,{" "}
              {receipt.seasons.map((s) => s.name).join(", ") || "no season"}
            </span>
          )}
          <span>{receipt.corpus_size} judged analyses in the training corpus</span>
        </div>
      </div>
    );
  }

  if (mode === "ask") {
    return (
      <div className="flag">
        <div className="flag-ask">
          <span>is this reading right?</span>
          <div className="spacer" />
          <button
            className="btn ghost small"
            disabled={busy}
            onClick={() => submit("correct")}
          >
            yes, it is right
          </button>
          <button className="btn small" disabled={busy} onClick={() => setMode("fixing")}>
            no, fix it
          </button>
        </div>
        {error && <p className="banner bad">{error}</p>}
      </div>
    );
  }

  return (
    <div className="flag">
      <div className="fix">
        <p className="hint">
          Change only what is wrong. The corrected labels go into the knowledge
          graph now and into the next fine-tuning run later.
        </p>

        {groups.map((g) => {
          const predicted = analysis.tags[g].label;
          const value = fixes[g] ?? predicted;
          return (
            <div className="fix-row" key={g}>
              <label className="group" htmlFor={`fix-${g}`}>
                {g}
              </label>
              <select
                id={`fix-${g}`}
                value={value}
                data-changed={value !== predicted}
                onChange={(e) => setFixes({ ...fixes, [g]: e.target.value })}
              >
                {ontology?.attributes[g].map((option) => (
                  <option key={option} value={option}>
                    {option}
                    {option === predicted ? "  (model said this)" : ""}
                  </option>
                ))}
              </select>
            </div>
          );
        })}

        <div className="fix-row">
          <label className="group" htmlFor="fix-note">
            note
          </label>
          <textarea
            id="fix-note"
            placeholder="optional: what is it really, if none of the labels fit"
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
        </div>

        {error && <p className="banner bad">{error}</p>}

        <div className="controls" style={{ marginTop: 0 }}>
          <span className="group" style={{ fontFamily: "var(--mono)", fontSize: 11 }}>
            {changed.length} label{changed.length === 1 ? "" : "s"} changed
          </span>
          <div className="spacer" />
          <button
            className="btn ghost small"
            onClick={() => {
              setMode("ask");
              setFixes({});
              setError(null);
            }}
            disabled={busy}
          >
            cancel
          </button>
          <button
            className="btn small"
            onClick={() => submit("wrong")}
            disabled={busy || (changed.length === 0 && !note.trim())}
          >
            {busy && <span className="spin" />}
            send correction
          </button>
        </div>
      </div>
    </div>
  );
}
