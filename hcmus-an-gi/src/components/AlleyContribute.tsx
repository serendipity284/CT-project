import type { CampusId } from '../lib/campuses';
import { useEffect, useState } from 'react';
import { contributeRoute, fetchEntrances, type Entrance } from '../lib/alleyApi';

type Step = { name: string; instruction: string; distance: string };
type Props = { placeId: number; campus: CampusId; onDone?: () => void };

const emptyStep = (): Step => ({ name: '', instruction: '', distance: '' });
const num = (s: string) => (s.trim() === '' ? undefined : Number(s));

export function AlleyContribute({ placeId, campus, onDone }: Props) {
  const [entrances, setEntrances] = useState<Entrance[]>([]);
  const [entId, setEntId] = useState<string>('new');
  const [newEnt, setNewEnt] = useState({ name: '', lat: '', lng: '' });
  const [steps, setSteps] = useState<Step[]>([emptyStep()]);
  const [finalInstr, setFinalInstr] = useState('');
  const [finalDist, setFinalDist] = useState('');
  const [msg, setMsg] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => { fetchEntrances(campus).then(setEntrances).catch(() => {}); }, [campus]);

  const setStep = (i: number, patch: Partial<Step>) =>
    setSteps((arr) => arr.map((s, k) => (k === i ? { ...s, ...patch } : s)));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMsg('');
    try {
      const body = {
        place_id: placeId,
        ...(entId === 'new'
          ? { entrance: { name: newEnt.name, lat: Number(newEnt.lat), lng: Number(newEnt.lng) } }
          : { entrance_node_id: Number(entId) }),
        steps: steps
          .filter((s) => s.name.trim() || s.instruction.trim())
          .map((s) => ({ name: s.name, instruction: s.instruction, distance_m: num(s.distance) })),
        final_instruction: finalInstr,
        final_distance_m: num(finalDist),
      };
      await contributeRoute(body);
      setMsg('Cảm ơn bạn! Tuyến đường đã được lưu.');
      onDone?.();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'Không gửi được');
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="alley-form" onSubmit={submit}>
      <h4 className="alley-h">Đóng góp đường vào hẻm</h4>
      <label>Cổng hẻm
        <select value={entId} onChange={(e) => setEntId(e.target.value)}>
          <option value="new">+ Tạo cổng mới</option>
          {entrances.map((en) => <option key={en.id} value={en.id}>{en.name}</option>)}
        </select>
      </label>
      {entId === 'new' && (
        <div className="alley-row">
          <input placeholder="Tên cổng hẻm" value={newEnt.name} required
            onChange={(e) => setNewEnt({ ...newEnt, name: e.target.value })} />
          <input placeholder="Vĩ độ" inputMode="decimal" value={newEnt.lat} required
            onChange={(e) => setNewEnt({ ...newEnt, lat: e.target.value })} />
          <input placeholder="Kinh độ" inputMode="decimal" value={newEnt.lng} required
            onChange={(e) => setNewEnt({ ...newEnt, lng: e.target.value })} />
        </div>
      )}
      <p className="alley-note">Các điểm mốc theo thứ tự từ cổng đi vào:</p>
      {steps.map((s, i) => (
        <div className="alley-row" key={i}>
          <input placeholder="Điểm mốc (vd: Cây me)" value={s.name} onChange={(e) => setStep(i, { name: e.target.value })} />
          <input placeholder="Hướng dẫn tới đây" value={s.instruction} onChange={(e) => setStep(i, { instruction: e.target.value })} />
          <input placeholder="m" inputMode="decimal" value={s.distance} onChange={(e) => setStep(i, { distance: e.target.value })} />
          <button type="button" className="alley-link" onClick={() => setSteps((a) => a.filter((_, k) => k !== i))}>Xóa</button>
        </div>
      ))}
      {steps.length < 12 && (
        <button type="button" className="alley-link" onClick={() => setSteps((a) => [...a, emptyStep()])}>+ Thêm điểm mốc</button>
      )}
      <div className="alley-row">
        <input placeholder="Hướng dẫn cuối: tới quán (vd: Quán bên phải)" value={finalInstr} required minLength={4}
          onChange={(e) => setFinalInstr(e.target.value)} />
        <input placeholder="m" inputMode="decimal" value={finalDist} onChange={(e) => setFinalDist(e.target.value)} />
      </div>
      <button className="alley-btn" disabled={busy}>{busy ? 'Đang gửi…' : 'Gửi đóng góp'}</button>
      {msg && <p className="alley-note">{msg}</p>}
    </form>
  );
}

export default AlleyContribute;
