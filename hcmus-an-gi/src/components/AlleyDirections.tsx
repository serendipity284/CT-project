import { useEffect, useState } from 'react';
import type { Origin } from '../lib/geo';
import { walkMinutesFromMeters } from '../lib/geo';
import { fetchDirections, type Directions } from '../lib/alleyApi';

type Props = {
  placeId: number;
  /** Điểm xuất phát (GPS hoặc cổng trường) — đổi là tự tính lại */
  origin: Origin;
  onResult?: (d: Directions | null) => void; // để PlacePage vẽ đường lên bản đồ
  onNoData?: () => void; // mở form đóng góp
};

export function AlleyDirections({ placeId, origin, onResult, onNoData }: Props) {
  const [data, setData] = useState<Directions | null>(null);
  const [err, setErr] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setErr('');
    fetchDirections(placeId, origin)
      .then((d) => {
        if (cancelled) return;
        setData(d);
        onResult?.(d);
      })
      .catch((e) => {
        if (cancelled) return;
        setData(null);
        onResult?.(null);
        setErr(e instanceof Error ? e.message : 'Không lấy được chỉ đường');
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [placeId, origin.lat, origin.lng]);

  if (loading && !data) return <p className="alley-note">Đang tìm đường…</p>;
  if (err) return <p className="alley-error">{err}</p>;
  if (!data) return null;

  return (
    <section className="alley-dir">
      <h4 className="alley-h">Từ {origin.source === 'gps' ? 'vị trí của bạn' : origin.label} đến cổng hẻm</h4>
      <p>
        {data.stage1_polyline.length
          ? `${data.stage1_distance_m} m · khoảng ${walkMinutesFromMeters(data.stage1_distance_m)} phút đi bộ`
          : 'Chưa vẽ được đường đến cổng hẻm.'}
      </p>
      <h4 className="alley-h">Trong hẻm ({data.stage2_total_m} m)</h4>
      {data.has_alley_data ? (
        <ol className="alley-steps">
          {data.stage2.map((s) => (
            <li key={s.node_id} className={`alley-step alley-${s.node_type}`}>
              <strong>{s.node_name}</strong>
              <span>{s.instruction}</span>
              {s.distance_m > 0 && <em>{Math.round(s.distance_m)} m</em>}
              {s.image_url && <img src={s.image_url} alt={s.node_name} loading="lazy" />}
            </li>
          ))}
        </ol>
      ) : (
        <p className="alley-note">
          Quán này chưa có hướng dẫn đi trong hẻm.{' '}
          {onNoData && (
            <button type="button" className="alley-link" onClick={onNoData}>
              Bạn biết đường? Đóng góp
            </button>
          )}
        </p>
      )}
    </section>
  );
}

export default AlleyDirections;
