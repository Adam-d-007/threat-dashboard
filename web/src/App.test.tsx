import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { LangProvider } from "./i18n";
import { dataAge } from "./lib/age";
import { slotKey } from "./lib/data";
import fixture from "./test/fixture-latest.json";

// The fixture run finished at 2026-10-22T11:00Z.
const at = (iso: string) => () => new Date(iso);

function mockFetch(body: unknown, status = 200) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify(body), { status })),
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("dataAge", () => {
  const now = new Date("2026-10-22T21:00:00Z");
  it.each([
    ["2026-10-22T12:00:00Z", "fresh"],
    ["2026-10-22T11:00:00Z", "fresh"], // exactly 10 h is still normal
    ["2026-10-22T10:30:00Z", "amber"],
    ["2026-10-22T06:30:00Z", "red"],
  ])("finished %s is %s", (finished, level) => {
    expect(dataAge(finished, now).level).toBe(level);
  });
});

describe("slotKey", () => {
  it.each([
    ["2026-10-22T04:04:00Z", "2026-10-21T13"],
    ["2026-10-22T04:05:00Z", "2026-10-22T04"],
    ["2026-10-22T12:59:00Z", "2026-10-22T04"],
    ["2026-10-22T23:59:00Z", "2026-10-22T13"],
    ["2026-11-01T00:30:00Z", "2026-10-31T13"],
  ])("%s -> %s", (now, key) => {
    expect(slotKey(new Date(now))).toBe(key);
  });
});

describe("App", () => {
  it("shows items and a normal age shortly after a run", async () => {
    mockFetch(fixture);
    render(<LangProvider lang="en"><App now={at("2026-10-22T13:00:00Z")} /></LangProvider>);
    expect(await screen.findByText(/Items in this run \(6\)/)).toBeInTheDocument();
    expect(screen.getByTestId("age")).toHaveAttribute("data-level", "fresh");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith(expect.stringMatching(/latest\.json\?v=2026-10-22T04$/));
  });

  it("turns red when the data is more than 14 hours old", async () => {
    mockFetch(fixture);
    render(<LangProvider lang="en"><App now={at("2026-10-23T01:30:00Z")} /></LangProvider>);
    expect(await screen.findByText(/a scheduled run was probably missed/)).toBeInTheDocument();
    expect(screen.getByTestId("age")).toHaveAttribute("data-level", "red");
  });

  it("refuses an unknown schema version with an error panel", async () => {
    mockFetch({ ...fixture, schema_version: 2 });
    render(<LangProvider lang="en"><App now={at("2026-10-22T13:00:00Z")} /></LangProvider>);
    expect(await screen.findByRole("alert")).toHaveTextContent(/version 2/);
    expect(screen.queryByText(/Items in this run/)).not.toBeInTheDocument();
  });

  it("shows an error when the data cannot be loaded", async () => {
    mockFetch({}, 404);
    render(<LangProvider lang="en"><App now={at("2026-10-22T13:00:00Z")} /></LangProvider>);
    expect(await screen.findByRole("alert")).toHaveTextContent(/HTTP 404/);
  });

  it("switches to Slovak", async () => {
    mockFetch(fixture);
    render(<LangProvider lang="en"><App now={at("2026-10-22T13:00:00Z")} /></LangProvider>);
    await screen.findByText(/Items in this run/);
    await userEvent.click(screen.getByRole("button", { name: "SK" }));
    expect(screen.getByText(/Položky z tejto aktualizácie \(6\)/)).toBeInTheDocument();
    expect(document.documentElement.lang).toBe("sk");
  });
});
