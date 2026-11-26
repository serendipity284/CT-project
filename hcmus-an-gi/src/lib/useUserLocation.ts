import { useCallback, useEffect, useMemo, useState } from "react";
import { CAMPUSES, type CampusId } from "./campuses";
import { resolveOrigin, type Origin } from "./geo";

export type LocStatus = "idle" | "loading" | "gps" | "fallback";

export type UserLocation = {
  /** GPS nếu đã lấy được, ngược lại là cổng trường của cơ sở đang chọn */
  origin: Origin;
  status: LocStatus;
  /** Xin quyền + lấy vị trí (gọi khi người dùng bấm nút, không tự bật khi tải trang) */
  request: () => Promise<Origin>;
  /** Quay về cổng trường */
  reset: () => void;
};

export function useUserLocation(campus: CampusId): UserLocation {
  const [gps, setGps] = useState<Origin | null>(null);
  const [status, setStatus] = useState<LocStatus>("idle");

  useEffect(() => {
    setGps(null);
    setStatus("idle");
  }, [campus]);

  const request = useCallback(async () => {
    setStatus("loading");
    const o = await resolveOrigin(campus);
    if (o.source === "gps") {
      setGps(o);
      setStatus("gps");
    } else {
      setGps(null);
      setStatus("fallback");
    }
    return o;
  }, [campus]);

  const reset = useCallback(() => {
    setGps(null);
    setStatus("idle");
  }, []);

  const origin = useMemo<Origin>(() => {
    if (gps) return gps;
    const g = CAMPUSES[campus];
    return { lat: g.lat, lng: g.lng, source: "gate", label: `cổng trường ${g.short}` };
  }, [gps, campus]);

  return { origin, status, request, reset };
}
