import "leaflet/dist/leaflet.css";
import { CircleMarker, MapContainer, Popup, TileLayer } from "react-leaflet";
import { useChartColors } from "../charts/colors";
import { useLang } from "../i18n";
import { fmtDate } from "../lib/format";
import type { Event } from "../types/run";

/** Events as circles sized by severity; corroborated events are filled, the rest hollow.
 * Loaded lazily, because Leaflet is the heaviest dependency on the page. */
export default function IncidentMap({ events, center, zoom }: { events: Event[]; center: [number, number]; zoom: number }) {
  const { t, pick, locale } = useLang();
  const c = useChartColors();
  return (
    <MapContainer center={center} zoom={zoom} scrollWheelZoom={false} className="h-80 w-full rounded-lg sm:h-96">
      <TileLayer
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        maxZoom={12}
      />
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
              <strong>{pick(e.title_en, e.title_sk)}</strong>
              <br />
              {fmtDate(e.date, locale)} · {e.place!.name} · {t.eventTypes[e.event_type]} · {t.tableCols.severity}{" "}
              {e.severity}
              <br />
              <a href={`#evt-${e.id}`}>{t.table} →</a>
            </Popup>
          </CircleMarker>
        ))}
    </MapContainer>
  );
}
