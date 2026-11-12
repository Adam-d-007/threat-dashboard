import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderBadge } from "./badge";
import { LangProvider, type Lang } from "./i18n";
import { assemble, loadV2, type V2Files } from "./lib/v2";
import { SourcesPage } from "./pages/Sources";
import { Incidents } from "./terrorism/Incidents";
import geopolitics from "./test/v2/geopolitics.json";
import incidents from "./test/v2/incidents.json";
import reports from "./test/v2/reports.json";
import status from "./test/v2/status.json";
import summary from "./test/v2/summary.json";

// The files in test/v2 are written by the pipeline's own code (python -m
// monitor.tests.web_fixture web/src/test/v2): the Kraków incident with a follow-up on its
// timeline, one incident carried over from the old pipeline, three labelled reports.
const files = { status, summary, incidents, reports, geopolitics } as unknown as V2Files;
const copy = () => structuredClone(files);

afterEach(() => vi.unstubAllGlobals());

function withLang(ui: React.ReactNode, lang: Lang = "en") {
  return render(<LangProvider lang={lang}>{ui}</LangProvider>);
}

describe("the v2 files as a run", () => {
  it("turns incidents into events with their timelines and reports into items", () => {
    const run = assemble(copy());
    expect(run.run.status).toBe("ok");
    expect(run.events.map((e) => [e.country, e.item_ids.length])).toEqual([
      ["PL", 2],
      ["FR", 2],
    ]);
    expect(run.events[0].severity).toBe(5);
    expect(run.items).toHaveLength(3);
    expect(run.items.filter((i) => i.event_id === run.events[0].id)).toHaveLength(2);
    expect(run.items[0].classification?.status).toBe("llm");
    expect(run.terrorism?.SK.level).toBe(summary.terrorism.SK.level);
    expect(run.geopolitics?.brief?.lines[0].text_sk).toBe("Rokovania pokračovali.");
    expect(run.geopolitics?.brief?.written_at).toBe("2026-11-12T14:30:00Z");
    expect(run.status?.queue.labelled_24h).toBe(3);
  });

  it("has no brief when no theatre has text", () => {
    const f = copy();
    for (const t of f.geopolitics.theatres) t.lines = [];
    expect(assemble(f).geopolitics?.brief).toBeNull();
  });

  it("never turns an address that is not a web address into a link", () => {
    const f = copy();
    f.incidents.incidents[0].reports[1].url = "javascript:alert(1)";
    f.reports.reports[0].url = "data:text/html,x";
    const run = assemble(f);
    expect(run.events[0].urls).toHaveLength(1);
    expect(run.items).toHaveLength(2);
    expect(JSON.stringify(run.events) + JSON.stringify(run.items)).not.toMatch(/javascript:|data:text/);
  });
});

describe("loading the v2 files", () => {
  const byName = (over: Record<string, unknown> = {}) =>
    vi.fn(async (url: string) => {
      const name = url.split("/v2/")[1].split("?")[0];
      const bodies: Record<string, unknown> = {
        "status.json": status,
        "summary.json": summary,
        "incidents/current.json": incidents,
        "reports.json": reports,
        "geopolitics.json": geopolitics,
        ...over,
      };
      return bodies[name] === null ? new Response("", { status: 404 }) : new Response(JSON.stringify(bodies[name]));
    });

  it("fetches the five files once each, with the hour as cache key", async () => {
    const fetch = byName();
    vi.stubGlobal("fetch", fetch);
    const result = await loadV2("https://data.example", new Date("2026-11-12T15:10:00Z"));
    expect(result.kind).toBe("ok");
    expect(fetch.mock.calls.map((c) => c[0]).sort()).toEqual([
      "https://data.example/v2/geopolitics.json?v=2026-11-12T15",
      "https://data.example/v2/incidents/current.json?v=2026-11-12T15",
      "https://data.example/v2/reports.json?v=2026-11-12T15",
      "https://data.example/v2/status.json?v=2026-11-12T15",
      "https://data.example/v2/summary.json?v=2026-11-12T15",
    ]);
  });

  it("names the file that could not be loaded", async () => {
    vi.stubGlobal("fetch", byName({ "reports.json": null }));
    expect(await loadV2("https://data.example", new Date())).toEqual({ kind: "error", message: "reports.json: HTTP 404" });
  });

  it("refuses a file of a version it does not know", async () => {
    vi.stubGlobal("fetch", byName({ "summary.json": { ...summary, schema_version: 3 } }));
    expect(await loadV2("https://data.example", new Date())).toEqual({ kind: "unsupported", version: 3 });
  });
});

describe("incident timelines", () => {
  const run = assemble(copy());
  const table = (lang: Lang) =>
    withLang(<Incidents events={run.events} items={run.items} center={[50, 15]} zoom={4} asOf={run.run.finished_at} tesat={null} />, lang);

  it("lists an incident once, with its follow-ups under it in order", async () => {
    table("en");
    expect(screen.getAllByRole("link", { name: /A gunman opened fire on Kraków/ })).toHaveLength(1);
    const row = within(screen.getByRole("link", { name: /A gunman opened fire on Kraków/ }).closest("tr")!);
    expect(row.queryByText("The shooter died.")).not.toBeVisible();
    await userEvent.click(row.getByText("2 reports, oldest first"));
    expect(row.getByText("The shooter died.")).toBeVisible();
    expect(row.getByText("first report")).toBeInTheDocument();
    expect(row.getByText("update")).toBeInTheDocument();
    expect(row.getByRole("link", { name: "sme.sk" })).toHaveAttribute("href", run.events[0].reports![1].url);
  });

  it("says it in Slovak", () => {
    table("sk");
    expect(screen.getAllByText("2 správy, od najstaršej").length).toBeGreaterThan(0);
  });
});

describe("the status card on the sources page", () => {
  it("says what the last update did and offers the embed code", () => {
    withLang(<SourcesPage run={assemble(copy())} />, "en");
    expect(screen.getByText("Everything ran.")).toBeInTheDocument();
    expect(screen.getByText("0 articles waiting for classification")).toBeInTheDocument();
    expect(screen.getByText(/3 articles classified in the last 24 hours/)).toBeInTheDocument();
    expect(screen.getByText(/groq_120b 3/)).toBeInTheDocument();
    expect(screen.getByText(/<iframe src=".*\/badge\.html\?lang=en"/)).toBeInTheDocument();
  });

  it("is not there for the old pipeline's data, which has no status", () => {
    const { status: _none, ...old } = assemble(copy());
    withLang(<SourcesPage run={old} />, "en");
    expect(screen.queryByText("How the latest update went")).not.toBeInTheDocument();
  });

  it("counts waiting articles in Slovak", () => {
    const f = copy();
    f.status.queue.waiting_label = 3;
    withLang(<SourcesPage run={assemble(f)} />, "sk");
    expect(screen.getByText("Na klasifikáciu čakajú 3 články")).toBeInTheDocument();
  });
});

describe("the embeddable badge", () => {
  const draw = (now: string, lang: Lang = "sk", change: (f: V2Files) => void = () => {}) => {
    const f = copy();
    change(f);
    const root = document.createElement("div");
    renderBadge(root, f.summary, f.status, new Date(now), lang, "https://monitor.example/");
    return root;
  };

  it("shows the official level first and this site's estimate as unofficial, with the date", () => {
    const text = draw("2026-11-12T15:00:00Z").textContent!;
    expect(text.indexOf("Oficiálny stupeň (SIS)")).toBeGreaterThan(-1);
    expect(text.indexOf("Oficiálny stupeň (SIS)")).toBeLessThan(text.indexOf("Neoficiálny odhad"));
    expect(text).toMatch(/2Oficiálny stupeň \(SIS\)Zvýšený/);
    expect(text).toMatch(/Údaje z 12\. 11\. 2026/);
    expect(text).toMatch(/index \d+\/100/);
  });

  it("greys out and says so when the data is more than 24 hours old", () => {
    expect(draw("2026-11-12T15:00:00Z").querySelector(".badge")!.className).toBe("badge");
    const old = draw("2026-11-13T15:00:00Z");
    expect(old.querySelector(".badge")!.className).toBe("badge stale");
    expect(old.textContent).toContain("Údaje sú staršie ako 24 hodín.");
  });

  it("says when a level is missing instead of leaving a gap", () => {
    const text = draw("2026-11-12T15:00:00Z", "en", (f) => {
      f.summary.anchors = [];
      f.summary.terrorism = null;
    }).textContent!;
    expect(text).toContain("Official level (SIS)unavailable");
    expect(text).toContain("not computed yet");
  });

  it("links back to the site in a new tab", () => {
    const link = draw("2026-11-12T15:00:00Z").querySelector("a")!;
    expect(link.href).toBe("https://monitor.example/");
    expect(link.target).toBe("_blank");
    expect(link.rel).toBe("noopener");
  });
});
