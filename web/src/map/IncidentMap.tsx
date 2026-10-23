import { CircleMarker, Popup } from "react-leaflet";
import { useChartColors } from "../charts/colors";
import { MapFrame } from "./MapFrame";
import { useLang } from "../i18n";
import { fmtDate } from "../lib/format";
import type { Event } from "../types/run";

/** Events as circles sized by severity; corroborated events are filled, the rest hollow.
 * Loaded lazily, because Leaflet is the heaviest dependency on the page. */
export default function IncidentMap({ events, center, zoom }: { events: Event[]; center: [number, number]; zoom: number }) {
  const { t, pick, locale } = useLang();
  const c = useChartColors();
  return (
    <MapFrame center={center} zoom={zoom}>
      {events
        .filter((e) => e.place)
        .map((e) => (
          <CircleMarker
            key={e.id}
            center={[e.place!.lat, e.place!.lon]}
            radius={5 + e.severity * 2.5}
            pathOptions={{
              color: c["series-1"],
              weight: 2,
              fillColor: c["series-1"],
              fillOpacity: e.corroborated ? 0.55 : 0,
              dashArray: e.corroborated ? undefined : "4 3",
            }}
          >
            <Popup>
              {e.urls?.[0] ? (
                <a href={e.urls[0]} target="_blank" rel="noreferrer">
                  <strong>{pick(e.title_en, e.title_sk)}</strong> ↗
                </a>
              ) : (
                <strong>{pick(e.title_en, e.title_sk)}</strong>
              )}
              <br />
              {fmtDate(e.date, locale)} · {e.place!.name} · {t.eventTypes[e.event_type]} · {t.tableCols.severity}{" "}
              {e.severity}
              <br />
              <a href={`#evt-${e.id}`}>{t.table} →</a>
            </Popup>
          </CircleMarker>
        ))}
    </MapFrame>
  );
}
