import { useEffect, useRef, useState } from "react";
import { MAX_UPLOAD } from "../api";
import { Upload } from "./icons";

interface Props {
  file: File | null;
  preview: string | null;
  disabled: boolean;
  busy: boolean;
  save: boolean;
  canSave: boolean;
  brand: string;
  onBrandChange: (brand: string) => void;
  onPick: (file: File | null, rejection?: string) => void;
  onSaveChange: (save: boolean) => void;
  onAnalyse: () => void;
}

/**
 * The picker. Drag and drop, click, and paste all end in the same place, and
 * the size and type rules are checked here with the exact wording api.py uses,
 * so a person is never taught two different limits for the same upload.
 */
export default function Specimen({
  file,
  preview,
  disabled,
  busy,
  save,
  canSave,
  brand,
  onBrandChange,
  onPick,
  onSaveChange,
  onAnalyse,
}: Props) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);

  function take(candidate: File | undefined | null) {
    if (!candidate) return;
    if (!candidate.type.startsWith("image/")) {
      onPick(null, "that file is not an image the server can read");
      return;
    }
    if (candidate.size > MAX_UPLOAD) {
      onPick(null, `image over ${Math.round(MAX_UPLOAD / 1024 / 1024)}MB`);
      return;
    }
    onPick(candidate);
  }

  // paste is the fastest way in when the photo is already on the clipboard,
  // and it costs one listener
  useEffect(() => {
    function onPaste(e: ClipboardEvent) {
      if (disabled) return;
      const item = Array.from(e.clipboardData?.items ?? []).find((i) =>
        i.type.startsWith("image/")
      );
      if (item) take(item.getAsFile());
    }
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  });

  const sizeLabel = file
    ? `${(file.size / 1024 / 1024).toFixed(1)}MB`
    : `max ${Math.round(MAX_UPLOAD / 1024 / 1024)}MB`;

  return (
    <div>
      <div
        className="drop"
        role="button"
        tabIndex={disabled ? -1 : 0}
        aria-disabled={disabled}
        aria-label="choose a garment photo"
        data-over={over}
        onClick={() => !disabled && input.current?.click()}
        onKeyDown={(e) => {
          if (disabled) return;
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            input.current?.click();
          }
        }}
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setOver(false);
          if (!disabled) take(e.dataTransfer.files[0]);
        }}
      >
        <span className="drop-corner left">{file ? file.name.slice(0, 28) : "empty"}</span>
        <span className="drop-corner right">{sizeLabel}</span>

        {preview ? (
          <img className="drop-preview" src={preview} alt="the photo you chose" />
        ) : (
          <div className="drop-inner">
            <span className="drop-icon">
              <Upload />
            </span>
            <strong>drop a garment photo</strong>
            <small>
              or <span style={{ textDecoration: "underline" }}>click to pick</span>, or
              paste from the clipboard
            </small>
          </div>
        )}

        <input
          ref={input}
          type="file"
          accept="image/*"
          className="sr-only"
          onChange={(e) => {
            take(e.target.files?.[0]);
            e.target.value = ""; // picking the same file twice must still fire
          }}
        />
      </div>

      <label className="brand-field">
        <span>
          brand <em>optional</em>
        </span>
        <input
          type="text"
          value={brand}
          placeholder="e.g. Zara, Nike, Gucci — used to estimate a price"
          disabled={disabled}
          onChange={(e) => onBrandChange(e.target.value)}
        />
      </label>

      <div className="controls">
        <label className="check" data-disabled={!canSave}>
          <input
            type="checkbox"
            checked={save && canSave}
            disabled={!canSave}
            onChange={(e) => onSaveChange(e.target.checked)}
          />
          save this to the knowledge graph
        </label>

        <div className="spacer" />

        {file && (
          <button className="btn ghost small" onClick={() => onPick(null)} disabled={busy}>
            clear
          </button>
        )}
        <button className="btn" onClick={onAnalyse} disabled={disabled || busy || !file}>
          {busy && <span className="spin" />}
          {busy ? "working" : "analyse"}
        </button>
      </div>
    </div>
  );
}
