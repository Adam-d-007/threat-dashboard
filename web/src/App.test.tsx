import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { LangProvider, type Lang } from "./i18n";
import { dataAge } from "./lib/age";
import { slotKey } from "./lib/data";
import { parseRoute } from "./lib/format";
import sample from "./sample/latest.json";
import fixture from "./test/fixture-latest.json";

// The fixture run finished at 2026-10-22T11:00Z and has no scores, like production today.
const at = (iso: string) => () => new Date(iso);
const sis = {
  id: "anchor_sk_sis", country: "SK", name: "SIS NBAC", url: "https://www.sis.gov.sk/o-nas/nbac-sto.html",
  scale: ["1", "2", "3", "4"], raw: "2", level: 2, normalized: 0.333, since: "2017-08-23",
  as_of: "2026-10-22T11:00:00Z", status: "ok", error: null, text_hash: "x", detail: null, manual: false,
};
const realRun = { ...fixture, anchors: [sis] };

function mockFetch(body: unknown, status = 200) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) =>
      url.includes("timeseries") ? new Response("", { status: 404 }) : new Response(JSON.stringify(body), { status }),
    ),
  );
}

function renderAt(iso: string, lang: Lang = "en") {
  return render(
    <LangProvider lang={lang}>
      <App now={at(iso)} />
    </LangProvider>,
  );
}

beforeEach(() => {
  window.location.hash = "";
});
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

describe("routes", () => {
  it("falls back to the Slovak terrorism page", () => {
    expect(parseRoute("")).toBe("terrorism-sk");
    expect(parseRoute("#nonsense")).toBe("terrorism-sk");
    expect(parseRoute("#geopolitics")).toBe("geopolitics");
  });
});

describe("App with real data and no scores yet", () => {
  it("shows the official SIS level and says the indicator is not computed", async () => {
    mockFetch(realRun);
    renderAt("2026-10-22T13:00:00Z");
    expect(await screen.findByText("The indicator is not computed yet")).toBeInTheDocument();
    expect(screen.getByText(/since 23 Aug 2017/)).toBeInTheDocument();
    expect(screen.queryByText(/\/100/)).not.toBeInTheDocument(); // no invented index
    expect(screen.getByTestId("age")).toHaveAttribute("data-level", "fresh");
    expect(screen.getByText(/Latest reports/)).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith(expect.stringMatching(/latest\.json\?v=2026-10-22T04$/));
  });

  it("turns red when the data is more than 14 hours old", async () => {
    mockFetch(realRun);
    renderAt("2026-10-23T01:30:00Z");
    expect(await screen.findByText(/a scheduled run was probably missed/)).toBeInTheDocument();
    expect(screen.getByTestId("age")).toHaveAttribute("data-level", "red");
  });

  it("shows the big Slovak heading in Slovak", async () => {
    mockFetch(realRun);
    renderAt("2026-10-22T13:00:00Z", "sk");
    expect(
      await screen.findByRole("heading", { level: 1, name: "Monitoring aktuálnych hrozieb terorizmu na Slovensku" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Ukazovateľ sa zatiaľ nepočíta")).toBeInTheDocument();
  });

  it("refuses an unknown schema version with an error panel", async () => {
    mockFetch({ ...realRun, schema_version: 2 });
    renderAt("2026-10-22T13:00:00Z");
    expect(await screen.findByRole("alert")).toHaveTextContent(/version 2/);
    expect(screen.queryByText(/Latest reports/)).not.toBeInTheDocument();
  });

  it("shows an error when the data cannot be loaded", async () => {
    mockFetch({}, 404);
    renderAt("2026-10-22T13:00:00Z");
    expect(await screen.findByRole("alert")).toHaveTextContent(/HTTP 404/);
  });

  it("switches language", async () => {
    mockFetch(realRun);
    renderAt("2026-10-22T13:00:00Z");
    await screen.findByText("The indicator is not computed yet");
    await userEvent.click(screen.getByRole("button", { name: "SK" }));
    expect(screen.getByText("Ukazovateľ sa zatiaľ nepočíta")).toBeInTheDocument();
    expect(document.documentElement.lang).toBe("sk");
  });
});

describe("App with a provisional score", () => {
  it("shows the warming-up card and no level until two weeks of history exist", async () => {
    const terrorism = {
      SK: { ...sample.terrorism.SK, provisional: true, available_from: "2026-11-05" },
      EU: { ...sample.terrorism.EU, provisional: true, available_from: "2026-11-05" },
    };
    mockFetch({ ...realRun, terrorism });
    renderAt("2026-10-22T13:00:00Z");
    expect(await screen.findByText("The indicator is warming up")).toBeInTheDocument();
    expect(screen.getByText(/expected on 5 Nov 2026/)).toBeInTheDocument();
    expect(screen.queryByText("Dashboard indicator")).toBeInTheDocument(); // card label only
    expect(screen.queryByText(/\/100/)).not.toBeInTheDocument();
    expect(screen.queryByText("What makes up the index")).not.toBeInTheDocument();
  });
});

describe("App with sample scores", () => {
  it("labels sample data on the page and shows level, index and components", async () => {
    mockFetch(sample);
    renderAt("2026-10-22T14:00:00Z");
    expect(await screen.findByText(/SAMPLE DATA/)).toBeInTheDocument();
    expect(screen.getByText("Dashboard indicator")).toBeInTheDocument();
    expect(screen.getByText("37")).toBeInTheDocument();
    expect(screen.getByText("What makes up the index")).toBeInTheDocument();
    expect(screen.getByText(/Floor 2: corroborated attack/)).toBeInTheDocument();
  });

  it("folds the UK travel advice into one chip on the EU view", async () => {
    window.location.hash = "terrorism-eu";
    mockFetch(sample);
    renderAt("2026-10-22T14:00:00Z");
    const chips = (await screen.findByText("Official levels elsewhere")).parentElement!;
    expect(within(chips).getAllByText("FCDO")).toHaveLength(1);
    expect(within(chips).getByText("OCAM/CUTA")).toBeInTheDocument();
  });
});


describe("Phase 5: every panel renders in each special case", () => {
  const base = sample as unknown as Record<string, any>;
  const withSK = (patch: Record<string, unknown>) => ({
    ...base,
    terrorism: { ...base.terrorism, SK: { ...base.terrorism.SK, ...patch } },
  });

  it("compares the ideology mix with TE-SAT, attacks and arrests separately", async () => {
    const evt = (id: string, event_type: string, ideology: string) => ({ ...base.events[0], id, event_type, ideology });
    mockFetch({
      ...realRun,
      events: [evt("a", "plot_disrupted", "jihadist"), evt("b", "attack", "right_wing"), evt("c", "arrest", "jihadist")],
    });
    renderAt("2026-10-22T14:00:00Z");
    expect(await screen.findByText("This dashboard, last 90 days (2)")).toBeInTheDocument();
    expect(screen.getByText("TE-SAT 2026, EU 2025 (45)")).toBeInTheDocument();
    // Jihadist: 1 of our 2 attacks against 24 of TE-SAT's 45.
    const row = (name: string) => screen.getAllByText(name).find((e) => e.closest("li"))!.closest("li");
    expect(row("Jihadist")).toHaveTextContent("50 % · 53 %");
    expect(row("Right-wing")).toHaveTextContent("50 % · 11 %");
    await userEvent.click(screen.getByRole("button", { name: "Arrests" }));
    expect(screen.getByText("This dashboard, last 90 days (1)")).toBeInTheDocument();
    expect(screen.getByText("TE-SAT 2026, EU 2025 (486)")).toBeInTheDocument();
  });

  it("no events", async () => {
    mockFetch({ ...base, events: [], items: [] });
    renderAt("2026-10-22T14:00:00Z");
    expect(await screen.findByText("Dashboard indicator")).toBeInTheDocument();
    expect(screen.getAllByText("No events in this period.").length).toBeGreaterThan(0);
  });

  it("LLM fallback", async () => {
    mockFetch(withSK({ llm: { ...base.terrorism.SK.llm, status: "fallback", level: null, drivers: [] } }));
    renderAt("2026-10-22T14:00:00Z");
    expect(await screen.findByText(/language model was unavailable/)).toBeInTheDocument();
  });

  it("disagreement", async () => {
    mockFetch(withSK({ disagreement: true }));
    renderAt("2026-10-22T14:00:00Z");
    expect(await screen.findByText(/disagree by more than one level/)).toBeInTheDocument();
  });

  it("a failed source", async () => {
    mockFetch(base);
    renderAt("2026-10-22T14:00:00Z");
    expect(await screen.findByText(/1 source failed in this run/)).toBeInTheDocument();
  });

  it("an official level change", async () => {
    mockFetch(base);
    renderAt("2026-10-22T14:00:00Z");
    expect(await screen.findByText("Official level changes")).toBeInTheDocument();
    expect(screen.getByText(/OCAM\/CUTA: 2 → 3/)).toBeInTheDocument();
  });
});
