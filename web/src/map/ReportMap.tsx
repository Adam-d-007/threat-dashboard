import "leaflet/dist/leaflet.css";
import { CircleMarker, MapContainer, Popup, TileLayer } from "react-leaflet";
import { useChartColors } from "../charts/colors";
import { useLang } from "../i18n";
import { fmtDate } from "../lib/format";
import type { Item } from "../types/run";

/** Reports with a named place, one circle per place. Loaded lazily, like the incident map. */
export default function ReportMap({ items }: { items: Item[] }) {
  const { locale } = useLang();
  const c = useChartColors();
  return (
    <MapContainer center={[48, 22]} zoom={3} scrollWheelZoom={false} className="h-80 w-full rounded-lg sm:h-96">
      <TileLayer
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        maxZoom={12}
      />
      {items.flatMap((i) =>
        (i.classification?.places ?? []).map((p, n) => (
          <CircleMarker
            key={`${i.id}-${n}`}
            center={[p.lat, p.lon]}
            radius={7}
            pathOptions={{ color: c["series-1"], weight: 2, fillColor: c["series-1"], fillOpacity: 0.55 }}
          >
            <Popup>
              <strong>{i.title}</strong>
              <br />
              {fmtDate(i.published_at, locale)} · {p.name} ·{" "}
              <a href={i.url} target="_blank" rel="noopener noreferrer">
                {i.domain}
              </a>
            </Popup>
          </CircleMarker>
        )),
      )}
    </MapContainer>
  );
}
