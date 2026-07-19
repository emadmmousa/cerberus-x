import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ProxyToggle, parseProxyUrl } from "../components/ProxyToggle";

describe("parseProxyUrl", () => {
  it("parses oxylabs style urls", () => {
    const parsed = parseProxyUrl(
      "http://customer-x:s3cret@pr.oxylabs.io:7777",
    );
    expect(parsed).toEqual({
      username: "customer-x",
      password: "s3cret",
      host: "pr.oxylabs.io",
      port: 7777,
      protocol: "http",
    });
  });
});

describe("ProxyToggle settings", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("parses URL into fields and saves via PUT", async () => {
    const fetchMock = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (url === "/api/proxy/status") {
        return Promise.resolve({
          ok: true,
          json: async () => ({ configured: false }),
        });
      }
      if (url === "/api/proxy/settings" && (!init || init.method === undefined)) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            configured: false,
            source: "none",
            username: "",
            password_set: false,
            host: "",
            port: null,
            protocol: "http",
            proxy_url_redacted: "",
          }),
        });
      }
      if (url === "/api/proxy/settings" && init?.method === "PUT") {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            ok: true,
            configured: true,
            source: "redis",
            username: "customer-x",
            password_set: true,
            host: "pr.oxylabs.io",
            port: 7777,
            protocol: "http",
            proxy_url_redacted: "http://customer-x:***@pr.oxylabs.io:7777",
            redis: { ok: true },
            env: { ok: true },
            k8s: { ok: false, error: "not in cluster" },
          }),
        });
      }
      return Promise.resolve({ ok: true, json: async () => ({}) });
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <ProxyToggle
        enabled={false}
        onChange={() => {}}
        protocol="http"
        onProtocolChange={() => {}}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /proxy settings/i }));

    const urlInput = await screen.findByLabelText(/full proxy url/i);
    fireEvent.change(urlInput, {
      target: { value: "http://customer-x:s3cret@pr.oxylabs.io:7777" },
    });
    fireEvent.click(screen.getByRole("button", { name: /parse url/i }));

    await waitFor(() => {
      expect(screen.getByLabelText(/^username$/i)).toHaveValue("customer-x");
      expect(screen.getByLabelText(/^host$/i)).toHaveValue("pr.oxylabs.io");
    });

    fireEvent.click(screen.getByRole("button", { name: /save credentials/i }));

    await waitFor(() => {
      const putCall = fetchMock.mock.calls.find(
        (c) => c[0] === "/api/proxy/settings" && c[1]?.method === "PUT",
      );
      expect(putCall).toBeTruthy();
      const body = JSON.parse(String(putCall![1]?.body));
      expect(body.username).toBe("customer-x");
      expect(body.password).toBe("s3cret");
      expect(body.host).toBe("pr.oxylabs.io");
      expect(body.port).toBe(7777);
    });

    await waitFor(() => {
      expect(screen.getByText(/runtime: saved/i)).toBeInTheDocument();
      expect(screen.getByText(/Worker configured/i)).toBeInTheDocument();
    });
  });
});
