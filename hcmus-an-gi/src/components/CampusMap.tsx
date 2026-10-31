import { useEffect, useRef } from "react";
import { CAMPUSES, type CampusId } from "../lib/campuses";
import type { Place } from "../lib/places-data";

type Props = {
  campus: CampusId;
  places: Place[];
  activeId: number | null;
  routeCoords: [number, number][];
  onPick: (id: number) => void;
};

export function CampusMap({ campus, places, activeId, routeCoords, onPick }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const api = useRef<{ draw: () => void } | null>(null);
  const propsRef = useRef({ campus, places, activeId, routeCoords, onPick });
  propsRef.current = { campus, places, activeId, routeCoords, onPick };

  useEffect(() => {
    let dead = false;
    let map: import("maplibre-gl").Map | null = null;
    const markers: import("maplibre-gl").Marker[] = [];

    (async () => {
      const maplibregl = await import("maplibre-gl");
      if (dead || !host.current) return;
      const origin = CAMPUSES[propsRef.current.campus];
      map = new maplibregl.Map({
        container: host.current,
        style: "https://tiles.openfreemap.org/styles/liberty",
        center: [origin.lng, origin.lat],
        zoom: 15.8,
        pitch: 58,
        bearing: -20,
        attributionControl: false,
      });
      map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");

      const draw = () => {
        if (!map) return;
        markers.splice(0).forEach((m) => m.remove());
        const {
          campus: cId,
          places: list,
          activeId: aid,
          routeCoords: path,
          onPick: pick,
        } = propsRef.current;
        const gateOrigin = CAMPUSES[cId];
        const gate = document.createElement("div");
        gate.className = "gate-pin";
        gate.textContent = gateOrigin.short;
        markers.push(
          new maplibregl.Marker({ element: gate })
            .setLngLat([gateOrigin.lng, gateOrigin.lat])
            .addTo(map),
        );
        for (const p of list) {
          const el = document.createElement("button");
          el.type = "button";
          el.className = "food-pin" + (p.id === aid ? " is-active" : "");
          el.textContent = p.cuisine.slice(0, 1);
          el.addEventListener("click", () => pick(p.id));
          markers.push(
            new maplibregl.Marker({ element: el }).setLngLat([p.lng, p.lat]).addTo(map),
          );
        }
        const active = list.find((p) => p.id === aid) ?? null;
        const coords =
          path.length >= 2
            ? path
            : active
              ? [
                  [gateOrigin.lng, gateOrigin.lat] as [number, number],
                  [active.lng, active.lat] as [number, number],
                ]
              : [];
        const line = {
          type: "Feature" as const,
          properties: {},
          geometry: { type: "LineString" as const, coordinates: coords },
        };
        const src = map.getSource("walk") as import("maplibre-gl").GeoJSONSource | undefined;
        if (!src) {
          map.addSource("walk", { type: "geojson", data: line });
          map.addLayer({
            id: "walk-line",
            type: "line",
            source: "walk",
            layout: { "line-cap": "round", "line-join": "round" },
            paint: { "line-color": "#c2410c", "line-width": 5, "line-opacity": 0.92 },
          });
        } else src.setData(line);

        if (coords.length >= 2) {
          let minLng = coords[0]![0],
            maxLng = coords[0]![0],
            minLat = coords[0]![1],
            maxLat = coords[0]![1];
          for (const [lng, lat] of coords) {
            minLng = Math.min(minLng, lng);
            maxLng = Math.max(maxLng, lng);
            minLat = Math.min(minLat, lat);
            maxLat = Math.max(maxLat, lat);
          }
          map.fitBounds(
            [
              [minLng, minLat],
              [maxLng, maxLat],
            ],
            { padding: 60, pitch: 55, duration: 700, maxZoom: 17 },
          );
        } else {
          map.easeTo({
            center: [gateOrigin.lng, gateOrigin.lat],
            zoom: 15.6,
            pitch: 58,
            bearing: -20,
            duration: 500,
          });
        }
      };

      api.current = { draw };
      map.on("load", draw);
    })();

    return () => {
      dead = true;
      api.current = null;
      map?.remove();
    };
  }, []);

  useEffect(() => {
    api.current?.draw();
  }, [campus, places, activeId, routeCoords]);

  return <div ref={host} className="map-host" />;
}
