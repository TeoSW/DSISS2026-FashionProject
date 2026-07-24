import { shopLinks, shopQuery } from "../shop";

/**
 * "Where can I get one like this." The system sells nothing and quotes no
 * prices; it takes the garment as the model described it and opens each shop's
 * own live search, where the real prices and real discounts are. The links open
 * in a new tab so the wardrobe is never navigated away from.
 */
export default function Shop({
  attrs,
  compact = false,
}: {
  attrs: { color?: string | null; material?: string | null; category?: string | null };
  compact?: boolean;
}) {
  const query = shopQuery(attrs);
  const links = shopLinks(attrs);
  if (links.length === 0) return null;

  if (compact) {
    return (
      <details className="shop-compact">
        <summary>shop “{query}”</summary>
        <div className="shop-links">
          {links.map((l) => (
            <a key={l.retailer} href={l.url} target="_blank" rel="noopener noreferrer">
              {l.retailer}
            </a>
          ))}
        </div>
      </details>
    );
  }

  return (
    <div className="shop">
      <p className="shop-head">
        buy something like it — searches <b>“{query}”</b> on shops that quote
        their own live prices
      </p>
      <div className="shop-grid">
        {links.map((l) => (
          <a
            className="shop-card"
            key={l.retailer}
            href={l.url}
            target="_blank"
            rel="noopener noreferrer"
          >
            <span className="shop-name">{l.retailer}</span>
            <span className="shop-note">{l.note}</span>
            <span className="shop-go" aria-hidden="true">
              search →
            </span>
          </a>
        ))}
      </div>
      <p className="shop-fine">
        These open the shop's own results in a new tab. Prices and discounts are
        theirs, live, and nothing here is stored or affiliated.
      </p>
    </div>
  );
}
