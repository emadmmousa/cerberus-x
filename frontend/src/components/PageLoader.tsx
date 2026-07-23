/** Lightweight route fallback — avoids blank screen during lazy chunk load. */
export function PageLoader() {
  return (
    <div className="page-loader" role="status" aria-live="polite" aria-busy="true">
      <div className="page-loader__bar" />
      <p className="page-loader__text">Loading…</p>
    </div>
  );
}

export function SkeletonRows({ count = 4 }: { count?: number }) {
  return (
    <div className="skeleton-stack" aria-hidden="true">
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="skeleton skeleton--row" />
      ))}
    </div>
  );
}
