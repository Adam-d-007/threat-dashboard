import { lazy, Suspense, useEffect, useState } from "react";
import { Layout } from "./components/Layout";
import { Banner } from "./components/ui";
import { useLang } from "./i18n";
import { loadLatest, loadRun, loadRunIndex, loadTimeseries, type LoadResult } from "./lib/data";
import { parseRoute, type Route } from "./lib/format";
import { useTheme } from "./lib/theme";
import { GeopoliticsPage } from "./pages/Geopolitics";
import { SourcesPage } from "./pages/Sources";
import { TerrorismPage } from "./pages/Terrorism";
import type { Timeseries } from "./types/run";

const systemNow = () => new Date();
// The method page carries the Markdown renderer and SCORING.md: load it only when opened.
const MethodPage = lazy(() => import("./pages/Method").then((m) => ({ default: m.MethodPage })));

function useRoute(): Route {
  const [route, setRoute] = useState<Route>(() => parseRoute(window.location.hash));
  useEffect(() => {
    const onHash = () => setRoute(parseRoute(window.location.hash));
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  return route;
}

export default function App({ now = systemNow }: { now?: () => Date }) {
  const { t } = useLang();
  const [theme, setTheme] = useTheme();
  const route = useRoute();
  const [result, setResult] = useState<LoadResult | null>(null);
  const [timeseries, setTimeseries] = useState<Timeseries | null>(null);
  const [runIds, setRunIds] = useState<string[]>([]);
  const [picked, setPicked] = useState<string | null>(null);
  const [pickedResult, setPickedResult] = useState<LoadResult | null>(null);

  useEffect(() => {
    loadLatest(now()).then(setResult);
    loadRunIndex(now()).then(setRunIds, () => setRunIds([]));
    // The history feeds one chart only, so it loads after the main file and never blocks it.
    loadTimeseries(now()).then(setTimeseries, (e) => console.error(e));
  }, [now]);

  useEffect(() => {
    if (picked) loadRun(picked).then(setPickedResult);
  }, [picked]);

  const latestRun = result?.kind === "ok" ? result.run : null;
  const pickedRun = picked && pickedResult?.kind === "ok" ? pickedResult.run : null;
  const run = pickedRun ?? latestRun;

  return (
    <Layout
      route={route}
      run={run}
      now={now()}
      theme={theme}
      setTheme={setTheme}
      runIds={runIds}
      picked={picked}
      onPick={(id) => {
        setPickedResult(null);
        setPicked(id === runIds[0] ? null : id);
      }}
    >
      {picked && pickedResult?.kind === "error" && (
        <Banner tone="crit">{`${t.loadError} (${pickedResult.message})`}</Banner>
      )}
      {result === null && <p className="text-muted">{t.loading}</p>}
      {result?.kind === "error" && <Banner tone="crit">{`${t.loadError} (${result.message})`}</Banner>}
      {result?.kind === "unsupported" && <Banner tone="crit">{t.unsupported(String(result.version))}</Banner>}
      {run && route === "terrorism-sk" && <TerrorismPage run={run} region="SK" timeseries={timeseries} />}
      {run && route === "terrorism-eu" && <TerrorismPage run={run} region="EU" timeseries={timeseries} />}
      {run && route === "geopolitics" && <GeopoliticsPage run={run} />}
      {run && route === "sources" && <SourcesPage run={run} />}
      {route === "method" && (
        <Suspense fallback={<p className="text-muted">{t.loading}</p>}>
          <MethodPage />
        </Suspense>
      )}
    </Layout>
  );
}
