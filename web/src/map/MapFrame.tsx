import "leaflet/dist/leaflet.css";
import type { Map as LeafletMap } from "leaflet";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { MapContainer, TileLayer } from "react-leaflet";
import { useLang } from "../i18n";

/** The map both pages use: OpenStreetMap's own colours, mouse-wheel zoom, and a full-screen
 * view (Esc or the button closes it). */
export function MapFrame({ center, zoom, children }: { center: [number, number]; zoom: number; children: ReactNode }) {
  const { t } = useLang();
  const [full, setFull] = useState(false);
  const map = useRef<LeafletMap | null>(null);

  useEffect(() => {
    // Leaflet measures its container once; tell it the size changed.
    const resize = setTimeout(() => map.current?.invalidateSize(), 50);
    if (!full) return () => clearTimeout(resize);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setFull(false);
    };
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      clearTimeout(resize);
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [full]);

  return (
    // MapContainer applies className only when it is created, so the box around it sets the size.
    <div className={full ? "fixed inset-0 z-[1200] bg-page p-3" : "relative h-80 sm:h-96"}>
      <MapContainer
        ref={map}
        center={center}
        zoom={zoom}
        scrollWheelZoom
        className="h-full w-full rounded-lg"
      >
        <TileLayer
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          maxZoom={17}
        />
        {children}
      </MapContainer>
      <button
        type="button"
        onClick={() => setFull(!full)}
        className={`absolute z-[1100] rounded-md border border-line bg-surface px-2.5 py-1.5 text-sm text-ink shadow hover:bg-surface-2 ${full ? "right-6 top-6" : "right-3 top-3"}`}
      >
        {full ? `✕ ${t.mapExit}` : `⛶ ${t.mapFull}`}
      </button>
    </div>
  );
}
