// Mirrors the pydantic models in api.py. When that file changes, this one has
// to change with it; there is no code generation here on purpose, the contract
// is small enough to read.

export type Group = "category" | "material" | "style" | "color" | "sleeve";

export const GROUPS: Group[] = ["category", "material", "style", "color", "sleeve"];

export interface Tag {
  label: string;
  confidence: number;
}

export interface Season {
  name: string;
  temp_range: string;
  warmth_min?: number;
  warmth_max?: number;
  score?: number;
}

export interface Analysis {
  id: string | null;
  analysis_id: string;
  tags: Record<string, Tag>;
  warmth: number;
  layer: string;
  seasons: Season[];
  summary: string;
  cutout: string | null;
  saved: boolean;
}

export interface Health {
  ok: boolean;
  model: string;
  neo4j: boolean;
}

export interface Ontology {
  attributes: Record<string, string[]>;
  seasons: Season[];
  material_warmth: Record<string, number>;
  category_warmth: Record<string, { warmth: number; layer: string }>;
  sleeve_modifier: Record<string, number>;
}

export interface FeedbackResult {
  id: string;
  garment_id: string | null;
  verdict: "correct" | "wrong";
  corrections: Record<string, string>;
  warmth: number | null;
  layer: string | null;
  seasons: Season[];
  graph_updated: boolean;
  garment_updated: boolean;
  filed: boolean;
  corpus_size: number;
}

export type Region = "upper" | "lower" | "full" | "unplaced";

export interface WardrobeItem {
  id: string;
  warmth: number | null;
  layer: string | null;
  photo: string | null;
  image_path: string | null;
  created_at: string | null;
  category: string | null;
  region: Region;
  material: string | null;
  style: string | null;
  color: string | null;
  sleeve: string | null;
  category_confidence: number | null;
  material_confidence: number | null;
  color_confidence: number | null;
  corrected: boolean;
  seasons: { name: string; temp_range: string }[];
  photo_url: string | null;
}

export interface WardrobeResponse {
  region: string | null;
  regions: Partial<Record<Region, number>>;
  count: number;
  items: WardrobeItem[];
}

export interface Tally {
  name: string;
  n: number;
  confidence?: number | null;
  region?: string;
  warmth?: number | null;
  temp_range?: string;
  warmth_min?: number;
  warmth_max?: number;
}

export interface Insights {
  model: string;
  photos: { files: number; bytes: number };
  feedback: FeedbackStats["corpus"];
  corrections?: {
    confirmed: number;
    wrong: number;
    total: number;
    confusions: { group: string; predicted: string; actual: string; n: number }[];
  };
  graph: {
    totals: {
      garments: number;
      mean_warmth: number | null;
      human_edges: number;
      mean_confidence: number | null;
      attribute_edges: number;
      low_confidence_edges: number;
    };
    by_category: Tally[];
    by_material: Tally[];
    by_color: Tally[];
    by_style: Tally[];
    by_layer: Tally[];
    by_season: Tally[];
    warmth: { warmth: number; n: number }[];
    regions: Partial<Record<Region, number>>;
  };
}

export interface FeedbackStats {
  corpus: {
    total: number;
    confirmed: number;
    corrected: number;
    agreement: number | null;
    per_group: Record<string, number>;
    confusions: Record<string, Record<string, number>>;
    with_image: number;
    corpus: string;
  };
  graph: {
    confirmed: number;
    wrong: number;
    total: number;
    confusions: { group: string; predicted: string; actual: string; n: number }[];
  } | null;
}

export interface GarmentHit {
  id: string;
  category?: string;
  warmth?: number;
}

export interface GarmentQuery {
  filter: Record<string, string>;
  results: GarmentHit[];
}

export interface GraphStats {
  nodes: Record<string, number>;
  relationships: Record<string, number>;
}
