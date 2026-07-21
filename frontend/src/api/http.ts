/** Shared fetch with credentials + auth error handling. */

export class ApiError extends Error {
  status: number;
  body: string;

  constructor(status: number, message: string, body = "") {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

export type ApiFetchOptions = RequestInit & {
  /** Skip redirect on 401 (e.g. login page probes). */
  skipAuthRedirect?: boolean;
};

async function parseError(res: Response): Promise<string> {
  const text = await res.text();
  try {
    const data = JSON.parse(text) as { error?: string; detail?: string };
    return data.error ?? data.detail ?? text;
  } catch {
    return text || `HTTP ${res.status}`;
  }
}

export async function apiFetch(
  input: string,
  init: ApiFetchOptions = {},
): Promise<Response> {
  const { skipAuthRedirect, ...rest } = init;
  const headers = new Headers(rest.headers);
  if (rest.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(input, {
    ...rest,
    headers,
    credentials: "include",
  });
  if (res.status === 401 && !skipAuthRedirect) {
    const path = window.location.pathname;
    if (path !== "/login") {
      window.location.assign(`/login?next=${encodeURIComponent(path)}`);
    }
  }
  return res;
}

export async function apiJson<T>(
  input: string,
  init: ApiFetchOptions = {},
): Promise<T> {
  const res = await apiFetch(input, init);
  if (!res.ok) {
    throw new ApiError(res.status, await parseError(res));
  }
  return res.json() as Promise<T>;
}
