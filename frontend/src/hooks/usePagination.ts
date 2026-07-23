import { useEffect, useMemo, useState } from "react";
import { DEFAULT_PAGE_SIZES } from "../lib/pagination";

export type UsePaginationOptions = {
  pageSize?: number;
  pageSizeOptions?: readonly number[];
  /** Resets to page 1 when this value changes (e.g. search/filter key). */
  resetKey?: string | number;
};

export function usePagination<T>(
  items: readonly T[],
  options?: UsePaginationOptions,
) {
  const pageSizeOptions = options?.pageSizeOptions ?? DEFAULT_PAGE_SIZES;
  const initialSize = options?.pageSize ?? pageSizeOptions[0];
  const [pageSize, setPageSizeState] = useState(initialSize);
  const [page, setPage] = useState(1);

  useEffect(() => {
    setPage(1);
  }, [options?.resetKey]);

  const total = items.length;
  const totalPages = Math.max(1, Math.ceil(total / pageSize) || 1);

  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  const slice = useMemo(() => {
    const start = (page - 1) * pageSize;
    return items.slice(start, start + pageSize);
  }, [items, page, pageSize]);

  const rangeStart = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const rangeEnd = Math.min(page * pageSize, total);

  return {
    items: slice,
    page,
    pageSize,
    pageSizeOptions,
    total,
    totalPages,
    rangeStart,
    rangeEnd,
    hasPrev: page > 1,
    hasNext: page < totalPages,
    setPage,
    setPageSize: (size: number) => {
      setPageSizeState(size);
      setPage(1);
    },
    goFirst: () => setPage(1),
    goPrev: () => setPage((current) => Math.max(1, current - 1)),
    goNext: () => setPage((current) => Math.min(totalPages, current + 1)),
    goLast: () => setPage(totalPages),
  };
}
