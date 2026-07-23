import { buildPageNumbers, formatPageRange } from "../lib/pagination";

type Props = {
  page: number;
  totalPages: number;
  total: number;
  rangeStart: number;
  rangeEnd: number;
  pageSize: number;
  pageSizeOptions?: readonly number[];
  onPageChange: (page: number) => void;
  onPageSizeChange?: (size: number) => void;
  className?: string;
  label?: string;
};

export function ListPagination({
  page,
  totalPages,
  total,
  rangeStart,
  rangeEnd,
  pageSize,
  pageSizeOptions = [10, 25, 50],
  onPageChange,
  onPageSizeChange,
  className = "",
  label = "List pagination",
}: Props) {
  if (total === 0 || totalPages <= 1) return null;

  const pages = buildPageNumbers(page, totalPages);

  return (
    <nav
      className={`list-pagination ${className}`.trim()}
      aria-label={label}
    >
      <div className="list-pagination__range">
        <span className="list-pagination__range-label">Showing</span>
        <strong className="list-pagination__range-value">
          {formatPageRange(rangeStart, rangeEnd, total)}
        </strong>
      </div>

      <div className="list-pagination__controls">
        <button
          type="button"
          className="list-pagination__nav"
          aria-label="First page"
          disabled={page <= 1}
          onClick={() => onPageChange(1)}
        >
          «
        </button>
        <button
          type="button"
          className="list-pagination__nav"
          aria-label="Previous page"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          ‹
        </button>

        <div className="list-pagination__pages" role="group" aria-label="Page numbers">
          {pages.map((token, index) =>
            token === "ellipsis" ? (
              <span
                key={`ellipsis-${index}`}
                className="list-pagination__ellipsis"
                aria-hidden="true"
              >
                …
              </span>
            ) : (
              <button
                key={token}
                type="button"
                className={`list-pagination__page${
                  token === page ? " list-pagination__page--active" : ""
                }`}
                aria-label={`Page ${token}`}
                aria-current={token === page ? "page" : undefined}
                onClick={() => onPageChange(token)}
              >
                {token}
              </button>
            ),
          )}
        </div>

        <button
          type="button"
          className="list-pagination__nav"
          aria-label="Next page"
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
        >
          ›
        </button>
        <button
          type="button"
          className="list-pagination__nav"
          aria-label="Last page"
          disabled={page >= totalPages}
          onClick={() => onPageChange(totalPages)}
        >
          »
        </button>
      </div>

      {onPageSizeChange && pageSizeOptions.length > 1 && (
        <label className="list-pagination__size">
          <span className="list-pagination__size-label">Per page</span>
          <select
            className="list-pagination__size-select"
            value={pageSize}
            onChange={(e) => onPageSizeChange(Number(e.target.value))}
            aria-label="Items per page"
          >
            {pageSizeOptions.map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </label>
      )}
    </nav>
  );
}
