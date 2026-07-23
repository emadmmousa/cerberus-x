export const DEFAULT_PAGE_SIZES = [10, 25, 50] as const;

export type PageToken = number | "ellipsis";

/** Compact page number sequence with ellipsis for large page counts. */
export function buildPageNumbers(current: number, totalPages: number): PageToken[] {
  if (totalPages <= 0) return [];
  if (totalPages === 1) return [1];
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, index) => index + 1);
  }

  const pages: PageToken[] = [1];
  const windowStart = Math.max(2, current - 1);
  const windowEnd = Math.min(totalPages - 1, current + 1);

  if (windowStart > 2) pages.push("ellipsis");
  for (let page = windowStart; page <= windowEnd; page += 1) pages.push(page);
  if (windowEnd < totalPages - 1) pages.push("ellipsis");
  pages.push(totalPages);

  return pages;
}

export function formatPageRange(rangeStart: number, rangeEnd: number, total: number): string {
  if (total === 0) return "No items";
  if (rangeStart === rangeEnd) return `${rangeStart} of ${total}`;
  return `${rangeStart}–${rangeEnd} of ${total}`;
}
