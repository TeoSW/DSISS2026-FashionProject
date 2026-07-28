// Inline SVG, no icon library and no emoji: four glyphs is not worth a
// dependency, and an emoji renders differently on every machine the thesis is
// demonstrated on.

const base = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.6,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

export function Upload({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...base} aria-hidden="true">
      <path d="M12 16V4" />
      <path d="m7 9 5-5 5 5" />
      <path d="M4 17v2a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-2" />
    </svg>
  );
}

export function Aperture({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...base} aria-hidden="true">
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 3.5v17" />
      <path d="M19.4 7.8 4.6 16.2" />
      <path d="M4.6 7.8l14.8 8.4" />
    </svg>
  );
}

export function Sun({ size = 17 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...base} aria-hidden="true">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M19.1 4.9l-1.4 1.4M6.3 17.7l-1.4 1.4" />
    </svg>
  );
}

export function Moon({ size = 17 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...base} aria-hidden="true">
      <path d="M20 14.5A8.2 8.2 0 0 1 9.5 4 8.5 8.5 0 1 0 20 14.5Z" />
    </svg>
  );
}

export function Auto({ size = 17 }: { size?: number }) {
  // half light, half dark: the conventional glyph for "whatever the machine is
  // set to", which is this app's default and needs its own mark
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...base} aria-hidden="true">
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 3.5a8.5 8.5 0 0 1 0 17Z" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function Wash({ size = 13 }: { size?: number }) {
  // a laundry tub, the way a care label draws one
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...base} aria-hidden="true">
      <path d="M3 8.5 5 5h14l2 3.5" />
      <path d="M3 8.5h18v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z" />
      <path d="M6.5 13c1 -1 2.5 -1 3.5 0s2.5 1 3.5 0 2.5 -1 3.5 0" />
    </svg>
  );
}
