import type { ShopLink } from "./types";

// Where to buy something like this. The system does not sell anything and does
// not know any prices; it hands the garment's own description to shops that do,
// and lets their live results carry the real prices and real discounts. Nothing
// here is invented, which is the only honest way to answer "where can I get one"
// without a product feed of our own.
//
// Every entry is a real, stable search endpoint. The query is the garment as the
// model described it, so "black wool coat" goes straight into each shop's search.

interface Retailer {
  name: string;
  note: string;
  url: (query: string) => string;
}

const RETAILERS: Retailer[] = [
  {
    name: "Google Shopping",
    note: "compares prices and discounts across shops",
    url: (q) => `https://www.google.com/search?tbm=shop&q=${q}`,
  },
  {
    name: "Zalando",
    note: "large EU catalogue, frequent sales",
    url: (q) => `https://en.zalando.de/catalogue/?q=${q}`,
  },
  {
    name: "About You",
    note: "EU fashion marketplace",
    url: (q) => `https://www.aboutyou.com/search?term=${q}`,
  },
  {
    name: "ASOS",
    note: "wide range, own-brand and others",
    url: (q) => `https://www.asos.com/search/?q=${q}`,
  },
  {
    name: "H&M",
    note: "budget end of the same styles",
    url: (q) => `https://www2.hm.com/en_us/search-results.html?q=${q}`,
  },
];

/** A short, human search phrase from what the model saw: "blue denim jeans". */
export function shopQuery(attrs: {
  color?: string | null;
  material?: string | null;
  category?: string | null;
}): string {
  return [attrs.color, attrs.material, attrs.category].filter(Boolean).join(" ").trim();
}

/** Real search links to trustable fashion sites for a garment like this one. */
export function shopLinks(attrs: {
  color?: string | null;
  material?: string | null;
  category?: string | null;
}): ShopLink[] {
  const query = shopQuery(attrs);
  if (!query) return [];
  const encoded = encodeURIComponent(query);
  return RETAILERS.map((r) => ({
    retailer: r.name,
    note: r.note,
    url: r.url(encoded),
  }));
}
