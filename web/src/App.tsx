import { useEffect, useState } from "react";
import { Layout } from "./components/Layout";
import { Banner } from "./components/ui";
import { useLang } from "./i18n";
import { loadLatest, loadTimeseries, type LoadResult } from "./lib/data";
import { parseRoute, type Route } from "./lib/format";
import { useTheme } from "./lib/theme";
import { GeopoliticsPage } from "./pages/Geopolitics";
import { MethodPage } from "./pages/Method";
import { SourcesPage } from "./pages/Sources";
import { TerrorismPage } from "./pages/Terrorism";
import type { Timeseries } from "./types/run";

const systemNow = () => new Date();

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

  useEffect(() => {
    loadLatest(now()).then(setResult);
    // The history feeds one chart only, so it loads after the main file and never blocks it.
    loadTimeseries(now()).then(setTimeseries, (e) => console.error(e));
  }, [now]);

  const run = result?.kind === "ok" ? result.run : null;

  return (
    <Layout route={route} run={run} now={now()} theme={theme} setTheme={setTheme}>
      {result === null && <p className="text-muted">{t.loading}</p>}
      {result?.kind === "error" && <Banner tone="crit">{`${t.loadError} (${result.message})`}</Banner>}
      {result?.kind === "unsupported" && <Banner tone="crit">{t.unsupported(String(result.version))}</Banner>}
      {run && route === "terrorism-sk" && <TerrorismPage run={run} region="SK" timeseries={timeseries} />}
      {run && route === "terrorism-eu" && <TerrorismPage run={run} region="EU" timeseries={timeseries} />}
      {run && route === "geopolitics" && <GeopoliticsPage run={run} />}
      {run && route === "sources" && <SourcesPage run={run} />}
      {route === "method" && <MethodPage />}
    </Layout>
  );
}
